"""
Rug Detection Model Engine using pure Python standard library (json, math).
Optimized for Termux on Android.
Loads weights, biases, normalizations, and thresholds dynamically from rug_model_v2_devwallet.json.
"""

import json
import math
import os
from typing import Dict, Any, List, Tuple, Optional


class RugFilterML:
    """
    Standard-library powered Rug Classifier (Model V2 with Dev Wallet profiling).
    Loads model parameters dynamically from rug_model_v2_devwallet.json.
    No numpy dependencies required.
    """

    def __init__(self, model_path: str = "rug_model_v2_devwallet.json", weights_path: Optional[str] = None):
        # Support weights_path parameter for backwards compatibility
        self.model_path = model_path if not weights_path or not weights_path.endswith(".json") else weights_path
        self.total_trained_samples = 0
        self.load_model()

    def load_model(self):
        """
        1. Load JSON. Read feature_names, mean, std, weights, bias,
           threshold, and log1p straight from the file. Do not hardcode them.
        """
        target_path = self.model_path
        if not os.path.exists(target_path):
            alt_path = os.path.join(os.path.dirname(__file__), "rug_model_v2_devwallet.json")
            if os.path.exists(alt_path):
                target_path = alt_path
            else:
                raise FileNotFoundError(f"Rug model file not found at: {self.model_path} or {alt_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.feature_names: List[str] = data["feature_names"]
        self.mean: List[float] = [float(v) for v in data["mean"]]
        self.std: List[float] = [float(v) for v in data["std"]]
        self.weights: List[float] = [float(v) for v in data["weights"]]
        self.bias: float = float(data["bias"])
        self.threshold: float = float(data["threshold"])
        self.log1p: List[str] = list(data.get("log1p", []))
        self.feat_to_idx: Dict[str, int] = {name: i for i, name in enumerate(self.feature_names)}
        self.total_trained_samples = int(data.get("trained_rows", 0))

    def extract_features(
        self,
        token_data: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
        dex_data: Optional[Dict[str, Any]] = None,
        dev_stats: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """
        2. Build 20-element feature vector in exact order:
           [0] dev_buy_sol (dev's initial buy, in SOL)
           [1] liquidity_usd
           [2] top_holder_pct
           [3] is_social_missing (1 if token has no social links, else 0)
           [4]-[9] dev wallet age bucket, exactly one set to 1.0:
               [4] age < 0.1 days, [5] < 1 day, [6] < 7 days,
               [7] < 30 days, [8] < 365 days, [9] 365+ days
           [12]-[17] dev wallet txns bucket, exactly one set to 1.0:
               [12] < 10, [13] < 50, [14] < 200,
               [15] < 1000, [16] < 10000, [17] < 40000
           Special cases:
           - If dev wallet txns >= 40000 OR wallet lookup hit page cap:
             set [10] = 1.0 and [18] = 1.0 instead of any age/txns bucket.
           - If you have no dev wallet data at all for the token:
             set [11] = 1.0 and [19] = 1.0 instead of any age/txns bucket.
           Everything else stays 0.0.
        """
        meta = meta or {}
        dex_data = dex_data or {}
        x = [0.0] * 20

        # [0] dev_buy_sol
        raw_dev = token_data.get("solAmount") if token_data.get("solAmount") is not None else token_data.get("dev_buy_sol")
        dev_buy = float(raw_dev) if raw_dev is not None else 0.0
        x[0] = max(dev_buy, 0.0)

        # [1] liquidity_usd
        liq_usd = float(dex_data.get("liquidity_usd") or token_data.get("liquidity_usd") or 0.0)
        x[1] = max(liq_usd, 0.0)

        # [2] top_holder_pct
        init_buy_tokens = float(token_data.get("initialBuy") or 0.0)
        v_tokens = float(token_data.get("vTokensInBondingCurve") or 1_000_000_000.0)
        if "top_holder_pct" in token_data:
            x[2] = float(token_data["top_holder_pct"])
        elif v_tokens > 0:
            x[2] = init_buy_tokens / v_tokens
        else:
            x[2] = 0.0

        # [3] is_social_missing (1 if the token has no social links, else 0)
        twitter = meta.get("twitter") or dex_data.get("twitter")
        telegram = meta.get("telegram") or dex_data.get("telegram")
        website = meta.get("website") or dex_data.get("website")
        has_twitter = bool(twitter and len(str(twitter).strip()) > 5)
        has_telegram = bool(telegram and len(str(telegram).strip()) > 5)
        has_website = bool(website and len(str(website).strip()) > 7)
        has_any_social = has_twitter or has_telegram or has_website
        x[3] = 0.0 if has_any_social else 1.0

        # Dev wallet profiling
        if not dev_stats or not dev_stats.get("has_data"):
            # Special case: no dev wallet data at all
            x[11] = 1.0
            x[19] = 1.0
        elif dev_stats.get("txns", 0) >= 40000 or dev_stats.get("hit_page_cap"):
            # Special case: dev wallet txns >= 40000 OR wallet lookup hit page cap
            x[10] = 1.0
            x[18] = 1.0
        else:
            # Dev wallet age buckets [4]-[9]
            age = float(dev_stats.get("age_days", 0.0))
            if age < 0.1:
                x[4] = 1.0
            elif age < 1.0:
                x[5] = 1.0
            elif age < 7.0:
                x[6] = 1.0
            elif age < 30.0:
                x[7] = 1.0
            elif age < 365.0:
                x[8] = 1.0
            else:
                x[9] = 1.0

            # Dev wallet txns buckets [12]-[17]
            txns = int(dev_stats.get("txns", 0))
            if txns < 10:
                x[12] = 1.0
            elif txns < 50:
                x[13] = 1.0
            elif txns < 200:
                x[14] = 1.0
            elif txns < 1000:
                x[15] = 1.0
            elif txns < 10000:
                x[16] = 1.0
            else:  # < 40000
                x[17] = 1.0

        return x

    def predict(self, features: List[float]) -> float:
        """
        3. Score it exactly like this:
           - For each feature name in the JSON's log1p list: x[i] = log1p(max(x[i], 0))
           - Standardize: xs[i] = (x[i] - mean[i]) / std[i]
           - p_rug = 1 / (1 + exp(-(dot(weights, xs) + bias)))
        """
        x_calc = list(features)

        # Apply log1p transformation to specified features
        for feat_name in self.log1p:
            if feat_name in self.feat_to_idx:
                idx = self.feat_to_idx[feat_name]
                x_calc[idx] = math.log1p(max(x_calc[idx], 0.0))

        # Standardize: xs[i] = (x[i] - mean[i]) / std[i]
        xs = [
            (x_calc[i] - self.mean[i]) / self.std[i] if self.std[i] != 0.0 else 0.0
            for i in range(len(x_calc))
        ]

        # Dot product: dot(weights, xs) + bias
        z = sum(w * val for w, val in zip(self.weights, xs)) + self.bias

        # Sigmoid: 1 / (1 + exp(-z))
        if z > 35.0:
            return 1.0
        elif z < -35.0:
            return 0.0

        p_rug = 1.0 / (1.0 + math.exp(-z))
        return p_rug

    def is_vetoed(
        self,
        p_rug: float,
        features: Optional[List[float]] = None,
        token_data: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
        dex_data: Optional[Dict[str, Any]] = None,
        dev_stats: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Evaluate veto rules:
        0. Multi-Factor Dev Buy Security Gate (skin in game, anti-burner, genuine socials, no spam)
        1. Base ML model threshold (P(rug) >= threshold)
        2. Farmed/purchased dormant burner wallet guardrail:
           Aged wallets (> 30 days) with < 10 transactions.
        3. Dev dump risk guardrail:
           Dev buy >= 0.40 SOL on low-transaction wallets (< 50 txns).
        4. Zero socials guardrail:
           Token has no verified community links (Twitter/TG/Website).
        """
        import config

        # 0. Comprehensive Multi-Factor Dev Gate (when raw metadata is supplied)
        if token_data is not None:
            try:
                from dev_gate import evaluate_dev_gate
                dev_passed, dev_reason = evaluate_dev_gate(token_data, meta, dex_data, dev_stats)
                if not dev_passed:
                    return True, dev_reason
            except Exception:
                pass

        # Strict Dev Buy Veto: Dev must invest at least MIN_DEV_BUY_SOL (default 0.08 SOL)
        if features is not None and len(features) >= 1:
            dev_buy = features[0]
            min_dev_buy = float(getattr(config, "MIN_DEV_BUY_SOL", 0.08))
            if dev_buy < min_dev_buy:
                return True, f"DEV ZERO/LOW BUY: Dev bought {dev_buy:.4f} SOL (< {min_dev_buy:.2f} SOL required)"

        # 1. Base ML Model Threshold
        if p_rug >= self.threshold:
            return True, f"ML Risk {p_rug*100:.1f}% >= {self.threshold*100:.0f}%"

        # 2. Targeted Anti-Rug Guardrails (Feature-based Fallback)
        if features is not None and len(features) >= 20:
            dev_buy = features[0]
            social_missing = bool(features[3] == 1.0)
            age_30_365d = bool(features[8] == 1.0)
            age_gt_365d = bool(features[9] == 1.0)
            txns_lt_10 = bool(features[12] == 1.0)
            txns_10_50 = bool(features[13] == 1.0)

            # Block Farmed/Purchased Dormant Burner Wallets (e.g. 30-365d old with < 10 txns)
            if getattr(config, "BLOCK_FARMED_WALLETS", True):
                if (age_30_365d or age_gt_365d) and txns_lt_10:
                    return True, "FARMED WALLET: Aged (>30d) with < 10 txns"

            # Block Dev Dump Pattern (dev buying 0.40 - 0.60+ SOL with low txns)
            max_dev_buy = getattr(config, "MAX_DEV_BUY_SOL", 0.40)
            if dev_buy >= max_dev_buy and (txns_lt_10 or txns_10_50):
                return True, f"DEV DUMP RISK: Dev bought {dev_buy:.2f} SOL on low-txn wallet (<50 txns)"

            # Block Zero Socials
            if getattr(config, "REQUIRE_SOCIALS", True) and social_missing:
                return True, "ZERO SOCIALS: Token has no verified community links"

        return False, ""

    def explain(self, features: List[float], p_rug: float) -> List[Tuple[str, str, str]]:
        """Human-readable insights for UI logging."""
        insights = []
        dev_buy = features[0]
        if dev_buy < 0.05:
            insights.append(("DEV BUY", f"Dev bought {dev_buy:.4f} SOL (DANGER: ZERO/LOW BUY)", "DANGER"))
        elif dev_buy > 2.0:
            insights.append(("DEV BUY", f"Dev bought {dev_buy:.2f} SOL (Heavy)", "WARN"))
        else:
            insights.append(("DEV BUY", f"Dev bought {dev_buy:.2f} SOL", "GOOD"))

        # Socials
        if features[3] == 0.0:
            insights.append(("COMMUNITY", "Social links verified", "GOOD"))
        else:
            insights.append(("COMMUNITY", "NO SOCIALS DETECTED (High rug risk)", "DANGER"))

        # Wallet status
        if features[11] == 1.0:
            insights.append(("DEV WALLET", "No dev wallet history found (Missing data)", "WARN"))
        elif features[10] == 1.0:
            insights.append(("DEV WALLET", "High-volume wallet (>= 40k txns or capped)", "GOOD"))
        else:
            age_desc = "Unknown"
            if features[4] == 1.0: age_desc = "< 0.1 days (Fresh wallet)"
            elif features[5] == 1.0: age_desc = "< 1 day old"
            elif features[6] == 1.0: age_desc = "1 to 7 days old"
            elif features[7] == 1.0: age_desc = "7 to 30 days old"
            elif features[8] == 1.0: age_desc = "30 to 365 days old"
            elif features[9] == 1.0: age_desc = "> 365 days (Veteran wallet)"

            status = "GOOD" if (features[8] == 1.0 or features[9] == 1.0) else (
                "DANGER" if features[4] == 1.0 else "WARN"
            )
            insights.append(("DEV WALLET AGE", age_desc, status))

            # Txns
            tx_desc = "Unknown"
            if features[12] == 1.0: tx_desc = "< 10 txns"
            elif features[13] == 1.0: tx_desc = "10 to 50 txns"
            elif features[14] == 1.0: tx_desc = "50 to 200 txns"
            elif features[15] == 1.0: tx_desc = "200 to 1,000 txns"
            elif features[16] == 1.0: tx_desc = "1,000 to 10,000 txns"
            elif features[17] == 1.0: tx_desc = "10,000 to 40,000 txns"
            insights.append(("DEV TX COUNT", tx_desc, "GOOD" if features[16] == 1.0 or features[17] == 1.0 else "WARN"))

        return insights

    def save_weights(self):
        """Standard model weights are maintained in JSON."""
        pass

    def train_step(self, *args, **kwargs):
        """Placeholder for backward compatibility."""
        return None
