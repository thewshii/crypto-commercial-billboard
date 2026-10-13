"""
Multi-Factor Dev Buy Security Gate for Solana Pump.fun.
Tightens entry validation against sneaky micro-buy rugs (< 0.25 SOL) and incubated burner rugs:
1. Baseline Floor: Enforces strict minimum dev buy (MIN_DEV_BUY_SOL = 0.08).
2. Dev Wallet History: Minimum on-chain age (>= 1.0 day) and transaction count (>= 15 txns).
3. Social Authenticity: Validates real handle/channel slugs, blocks dummy root domains (x.com, t.me),
   and requires multi-social presence (>= 2 channels) for micro-buys.
4. Supply Concentration: Caps dev supply holding (<= 6.0%) on micro-buys to prevent dump leverage.
5. Spam/Phishing Blacklist: Filters test tokens, airdrops, claims, and copycat scams.
6. Incubated Farmed Wallets: Blocks 7-30 day accounts committing 0.30 - 2.0 SOL dev buys.
"""

import re
from typing import Dict, Any, Tuple, List, Optional
import config

SPAM_KEYWORDS = {
    "test", "testing", "sample", "dummy", "airdrop", "claim",
    "presale", "presales", "reward", "rewards", "official", "v2",
    "admin", "support", "bonus", "whitelist", "free"
}

DUMMY_DOMAINS = {
    "x.com", "twitter.com", "t.me", "telegram.org", "pump.fun",
    "google.com", "youtube.com", "placeholder", "none", "null",
    "n/a", "na", "t.co", "bit.ly", "example.com"
}


def validate_social_urls(
    meta: Optional[Dict[str, Any]] = None,
    dex_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Strict validation of project social links.
    Detects placeholder links (e.g. 'https://x.com', 'https://t.me') and generic root domains.
    Returns:
        {
            "valid_count": int,
            "has_twitter": bool,
            "has_telegram": bool,
            "has_website": bool,
            "twitter_url": str,
            "telegram_url": str,
            "website_url": str,
            "rejected": Dict[str, str]
        }
    """
    meta = meta or {}
    dex_data = dex_data or {}

    tw = str(meta.get("twitter") or dex_data.get("twitter") or "").strip()
    tg = str(meta.get("telegram") or dex_data.get("telegram") or "").strip()
    ws = str(meta.get("website") or dex_data.get("website") or "").strip()

    def check_url(url: str, kind: str) -> Tuple[bool, str]:
        if not url or len(url) < 8:
            return False, "Empty or URL too short (< 8 chars)"

        u_lower = url.lower()
        clean = re.sub(r"^https?://(www\.)?", "", u_lower).rstrip("/")
        if clean in DUMMY_DOMAINS:
            return False, f"Dummy root domain '{clean}' without handle or path"

        parts = clean.split("/")
        domain = parts[0]

        if kind == "twitter":
            if domain not in ("x.com", "twitter.com"):
                return False, f"Not an X/Twitter domain ('{domain}')"
            if len(parts) < 2 or len(parts[1]) < 3:
                return False, "Missing X/Twitter handle path"
            if parts[1] in ("home", "explore", "search", "hashtag", "i", "login", "signup", "intent"):
                return False, f"Generic Twitter navigation URL ('/{parts[1]}')"
            return True, "Valid"

        elif kind == "telegram":
            if domain not in ("t.me", "telegram.me"):
                return False, f"Not a Telegram domain ('{domain}')"
            if len(parts) < 2 or len(parts[1]) < 4:
                return False, "Missing Telegram channel/group slug"
            if parts[1] in ("joinchat", "share"):
                if len(parts) < 3 or len(parts[2]) < 4:
                    return False, "Incomplete Telegram invite slug"
            return True, "Valid"

        elif kind == "website":
            if domain in DUMMY_DOMAINS:
                return False, f"Dummy website domain ('{domain}')"
            if "." not in domain or len(domain) < 4:
                return False, f"Invalid domain structure ('{domain}')"
            return True, "Valid"

        return False, "Unknown platform"

    v_tw, r_tw = check_url(tw, "twitter")
    v_tg, r_tg = check_url(tg, "telegram")
    v_ws, r_ws = check_url(ws, "website")

    valid_count = sum([1 for v in (v_tw, v_tg, v_ws) if v])

    return {
        "valid_count": valid_count,
        "has_twitter": v_tw,
        "has_telegram": v_tg,
        "has_website": v_ws,
        "twitter_url": tw if v_tw else "",
        "telegram_url": tg if v_tg else "",
        "website_url": ws if v_ws else "",
        "rejected": {
            "twitter": r_tw if not v_tw and tw else "",
            "telegram": r_tg if not v_tg and tg else "",
            "website": r_ws if not v_ws and ws else ""
        }
    }


def check_spam_keywords(
    name: str,
    symbol: str,
    description: str = ""
) -> Tuple[bool, str]:
    """
    Detect scam, phishing, test, or copycat keywords in token metadata.
    """
    text = f"{name} {symbol} {description}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))

    for kw in SPAM_KEYWORDS:
        if kw in tokens:
            return True, f"Flagged scam/test keyword '{kw.upper()}'"

    return False, ""


def evaluate_dev_gate(
    token_data: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None,
    dex_data: Optional[Dict[str, Any]] = None,
    dev_stats: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Comprehensive multi-factor gate evaluating token quality and dev intent.
    Returns:
        (is_passed: bool, veto_reason: str)
    """
    meta = meta or {}
    dex_data = dex_data or {}
    dev_stats = dev_stats or {}

    symbol = str(token_data.get("symbol", "TOKEN")).upper()
    name = str(token_data.get("name", "Unknown"))
    desc = str(meta.get("description", ""))

    # -----------------------------------------------------------------
    # 1. Hard Dev Buy Floor
    # -----------------------------------------------------------------
    raw_dev = token_data.get("solAmount") if token_data.get("solAmount") is not None else token_data.get("dev_buy_sol")
    dev_buy = float(raw_dev) if raw_dev is not None else 0.0
    min_dev_buy = float(getattr(config, "MIN_DEV_BUY_SOL", 0.08))

    if dev_buy < min_dev_buy:
        return False, f"DEV ZERO/MICRO BUY: Dev bought {dev_buy:.4f} SOL (< {min_dev_buy:.2f} SOL required floor)"

    # -----------------------------------------------------------------
    # 2. Spam & Phishing Keyword Filter
    # -----------------------------------------------------------------
    if getattr(config, "BLOCK_SPAM_KEYWORDS", True):
        is_spam, spam_reason = check_spam_keywords(name, symbol, desc)
        if is_spam:
            return False, f"SPAM KEYWORD: {spam_reason} in ${symbol} ({name})"

    # -----------------------------------------------------------------
    # 3. Socials Validation
    # -----------------------------------------------------------------
    socials = validate_social_urls(meta, dex_data)
    valid_socials_count = socials["valid_count"]

    if getattr(config, "REQUIRE_SOCIALS", True) and valid_socials_count == 0:
        return False, "ZERO SOCIALS: Token has no verified community links (or all links are placeholders)"

    # -----------------------------------------------------------------
    # 4. Micro-Buy Scrutiny Zone (< DEV_BUY_SCRUTINY_THRESHOLD_SOL)
    # When dev commits < 0.25 SOL, enforce strict multi-factor requirements.
    # -----------------------------------------------------------------
    scrutiny_threshold = float(getattr(config, "DEV_BUY_SCRUTINY_THRESHOLD_SOL", 0.25))

    if dev_buy < scrutiny_threshold:
        # A. Dev Wallet History (Anti-Burner Check)
        if not dev_stats.get("has_data"):
            return False, f"UNVERIFIED DEV WALLET: Micro-buy ({dev_buy:.3f} SOL) with unconfirmed on-chain history"

        age_days = float(dev_stats.get("age_days", 0.0))
        txns = int(dev_stats.get("txns", 0))

        min_age = float(getattr(config, "MIN_DEV_WALLET_AGE_DAYS_LOW_BUY", 1.0))
        if age_days < min_age:
            return False, f"BURNER DEV WALLET: Micro-buy ({dev_buy:.3f} SOL) on fresh wallet ({age_days*24:.1f}h old < {min_age*24:.0f}h)"

        min_txns = int(getattr(config, "MIN_DEV_WALLET_TXNS_LOW_BUY", 15))
        if txns < min_txns:
            return False, f"BURNER DEV WALLET: Micro-buy ({dev_buy:.3f} SOL) with only {txns} txns (< {min_txns} required)"

        # B. Social Channel Depth (Require >= 2 verified channels on micro-buys)
        if getattr(config, "REQUIRE_MULTI_SOCIALS_LOW_BUY", True):
            if valid_socials_count < 2:
                # Exception: seasoned veteran dev wallet (> 30d and > 50 txns)
                if not (age_days >= 30.0 and txns >= 50):
                    return False, f"WEAK SOCIALS: Micro-buy ({dev_buy:.3f} SOL) requires at least 2 verified community channels (found {valid_socials_count})"

        # C. Supply Hoarding Cap
        init_buy_tokens = float(token_data.get("initialBuy") or 0.0)
        v_tokens = float(token_data.get("vTokensInBondingCurve") or 1_000_000_000.0)
        top_holder_pct = float(token_data.get("top_holder_pct") or (init_buy_tokens / v_tokens if v_tokens > 0 else 0.0))

        max_supply_pct = float(getattr(config, "MAX_DEV_SUPPLY_PCT_LOW_BUY", 0.060))
        if top_holder_pct > max_supply_pct:
            return False, f"SUPPLY HOARDING: Dev holds {top_holder_pct*100:.1f}% supply with only {dev_buy:.3f} SOL buy (> {max_supply_pct*100:.0f}% cap)"

        # D. Metadata Description Quality
        if len(desc.strip()) < 8 or desc.strip().lower() in ("test", "coin", "pump", "none", "n/a", "."):
            return False, f"LOW QUALITY METADATA: Micro-buy ({dev_buy:.3f} SOL) with blank/trivial description"

    # -----------------------------------------------------------------
    # 5. Farmed / Purchased Dormant Burner Guardrail (All Buy Sizes)
    # -----------------------------------------------------------------
    if getattr(config, "BLOCK_FARMED_WALLETS", True) and dev_stats.get("has_data"):
        age_days = float(dev_stats.get("age_days", 0.0))
        txns = int(dev_stats.get("txns", 0))
        if age_days >= 30.0 and txns < 10:
            return False, f"FARMED WALLET: Aged ({age_days:.0f}d) with < 10 txns ({txns} txns)"

    # -----------------------------------------------------------------
    # 6. Incubated Farmed Wallet Guardrail (0.30 - 2.00 SOL & 7 - 30 Days Old)
    # Mitigates the syndicate attack vector where wallets are aged 1-4 weeks
    # and funded with 0.30 - 2.0 SOL to bypass fresh-burner and micro-buy gates.
    # -----------------------------------------------------------------
    if getattr(config, "BLOCK_INCUBATED_WALLETS", True) and dev_stats.get("has_data"):
        age_days = float(dev_stats.get("age_days", 0.0))
        txns = int(dev_stats.get("txns", 0))

        inc_min_buy = float(getattr(config, "INCUBATED_BUY_MIN_SOL", 0.30))
        inc_max_buy = float(getattr(config, "INCUBATED_BUY_MAX_SOL", 2.00))
        inc_min_age = float(getattr(config, "INCUBATED_AGE_MIN_DAYS", 7.0))
        inc_max_age = float(getattr(config, "INCUBATED_AGE_MAX_DAYS", 30.0))
        inc_block_outright = getattr(config, "INCUBATED_BLOCK_OUTRIGHT", True)
        inc_min_txns = int(getattr(config, "INCUBATED_MIN_TXNS", 60))
        inc_require_multi_socials = getattr(config, "INCUBATED_REQUIRE_MULTI_SOCIALS", True)
        inc_max_supply_pct = float(getattr(config, "INCUBATED_MAX_SUPPLY_PCT", 0.10))

        if inc_min_buy <= dev_buy <= inc_max_buy and inc_min_age <= age_days <= inc_max_age:
            if inc_block_outright:
                return False, (
                    f"INCUBATED FARMED WALLET: Dev bought {dev_buy:.2f} SOL on {age_days:.1f}d account "
                    f"({txns} txns) — matches 0.30-2.0 SOL / 7-30d rug vulnerability"
                )

            # Scrutiny mode (if outright blocking is disabled via config)
            if txns < inc_min_txns:
                return False, (
                    f"INCUBATED FARMED WALLET: Dev bought {dev_buy:.2f} SOL on {age_days:.1f}d account "
                    f"with only {txns} txns (< {inc_min_txns} required)"
                )

            if inc_require_multi_socials and valid_socials_count < 2:
                return False, (
                    f"INCUBATED FARMED WALLET: Dev bought {dev_buy:.2f} SOL on {age_days:.1f}d account "
                    f"with weak socials ({valid_socials_count} < 2 channels)"
                )

            init_buy_tokens = float(token_data.get("initialBuy") or 0.0)
            v_tokens = float(token_data.get("vTokensInBondingCurve") or 1_000_000_000.0)
            top_holder_pct = float(token_data.get("top_holder_pct") or (init_buy_tokens / v_tokens if v_tokens > 0 else 0.0))
            if top_holder_pct > inc_max_supply_pct:
                return False, (
                    f"INCUBATED FARMED WALLET: Dev holds {top_holder_pct*100:.1f}% supply with {dev_buy:.2f} SOL buy "
                    f"(> {inc_max_supply_pct*100:.0f}% cap)"
                )

    # -----------------------------------------------------------------
    # 7. Dev Dump Pattern Guardrail (All Buy Sizes)
    # -----------------------------------------------------------------
    max_dev_buy = float(getattr(config, "MAX_DEV_BUY_SOL", 0.40))
    if dev_buy >= max_dev_buy and dev_stats.get("has_data"):
        txns = int(dev_stats.get("txns", 0))
        if txns < 50:
            return False, f"DEV DUMP RISK: Dev bought {dev_buy:.2f} SOL on low-txn wallet ({txns} txns < 50)"

    return True, ""
