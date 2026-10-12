"""
Paper Trading / Demo Trading Engine.
Simulates realistic Solana buys and sells on pump.fun bonding curves,
tracks demo balance, P&L, positions, and triggers online ML model updates.
"""

import time
import secrets
from typing import Dict, Any, Optional, List
import config
from config import (
    DEMO_INITIAL_BALANCE_SOL,
    DEFAULT_BUY_AMOUNT_SOL,
    MAX_OPEN_POSITIONS,
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT
)
ENABLE_ONLINE_LEARNING = getattr(config, "ENABLE_ONLINE_LEARNING", False)


def generate_simulated_tx_hash() -> str:
    """Generate a realistic 88-character Base58 Solana transaction signature."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(88))


class DemoPosition:
    def __init__(
        self,
        mint: str,
        symbol: str,
        name: str,
        curve_key: str,
        entry_price_sol: float,
        entry_sol_amount: float,
        tokens_amount: float,
        initial_curve_sol: float,
        features: List[float],
        p_rug: float
    ):
        self.mint = mint
        self.symbol = symbol
        self.name = name
        self.curve_key = curve_key
        self.entry_price_sol = entry_price_sol
        self.entry_sol_amount = entry_sol_amount
        self.tokens_amount = tokens_amount
        self.initial_curve_sol = initial_curve_sol
        self.features = features
        self.p_rug = p_rug
        self.entry_time = time.time()
        self.tx_hash = generate_simulated_tx_hash()

        # Dynamic tracking
        self.highest_price_sol = entry_price_sol
        self.current_price_sol = entry_price_sol
        self.current_pnl_pct = 0.0
        self.is_closed = False
        self.close_reason = ""
        self.realized_sol = 0.0


class PaperTradingEngine:
    def __init__(self, initial_balance: float = DEMO_INITIAL_BALANCE_SOL, ml_engine=None):
        self.balance_sol = initial_balance
        self.initial_balance = initial_balance
        self.ml_engine = ml_engine
        self.positions: Dict[str, DemoPosition] = {}
        self.trade_history: List[Dict[str, Any]] = []

        # Performance stats
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.total_realized_pnl_sol = 0.0
        self.best_win_pct = 0.0
        self.worst_loss_pct = 0.0

    def can_buy(self, buy_amount: float = DEFAULT_BUY_AMOUNT_SOL) -> bool:
        """Check if demo wallet has enough balance and slots."""
        if not getattr(config, "YOLO_MODE", False):
            if len(self.positions) >= MAX_OPEN_POSITIONS:
                return False
        if self.balance_sol < buy_amount:
            return False
        return True

    def execute_demo_buy(
        self,
        token_data: Dict[str, Any],
        p_rug: float,
        features: List[float],
        buy_amount: float = DEFAULT_BUY_AMOUNT_SOL
    ) -> Optional[DemoPosition]:
        """
        Simulate a buy transaction on the pump.fun bonding curve.
        """
        mint = token_data.get("mint")
        if not mint or mint in self.positions:
            return None

        if not self.can_buy(buy_amount):
            return None

        # Calculate entry price and tokens acquired from bonding curve
        v_tokens = float(token_data.get("vTokensInBondingCurve") or 1073000000.0)
        v_sol = float(token_data.get("vSolInBondingCurve") or 30.0)
        k = v_tokens * v_sol

        new_v_sol = v_sol + buy_amount
        new_v_tokens = k / new_v_sol
        tokens_bought = v_tokens - new_v_tokens
        entry_price = buy_amount / tokens_bought if tokens_bought > 0 else (v_sol / v_tokens)

        # Deduct demo balance
        self.balance_sol -= buy_amount

        curve_key = token_data.get("bondingCurveKey", "")
        if not curve_key:
            from onchain import derive_bonding_curve
            curve_key = derive_bonding_curve(mint) or ""

        pos = DemoPosition(
            mint=mint,
            symbol=token_data.get("symbol", "TOKEN"),
            name=token_data.get("name", "Unknown"),
            curve_key=curve_key,
            entry_price_sol=entry_price,
            entry_sol_amount=buy_amount,
            tokens_amount=tokens_bought,
            initial_curve_sol=float(token_data.get("solAmount") or 0.3),
            features=features,
            p_rug=p_rug
        )

        self.positions[mint] = pos
        return pos

    def execute_demo_sell(
        self,
        mint: str,
        reason: str,
        current_price_sol: float
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate selling a demo position and finalize P&L.
        """
        pos = self.positions.get(mint)
        if not pos or pos.is_closed:
            return None

        pos.current_price_sol = current_price_sol
        if pos.entry_price_sol > 0:
            pnl_pct = ((current_price_sol - pos.entry_price_sol) / pos.entry_price_sol) * 100.0
        else:
            pnl_pct = 0.0

        pos.current_pnl_pct = pnl_pct
        pos.is_closed = True
        pos.close_reason = reason

        # Calculate returned SOL
        # Avoid negative returned sol
        sol_received = max(pos.entry_sol_amount * (1.0 + (pnl_pct / 100.0)), 0.0)
        pnl_sol = sol_received - pos.entry_sol_amount

        self.balance_sol += sol_received
        self.total_realized_pnl_sol += pnl_sol
        self.total_trades += 1

        is_win = pnl_sol > 0
        if is_win:
            self.wins += 1
            if pnl_pct > self.best_win_pct:
                self.best_win_pct = pnl_pct
        else:
            self.losses += 1
            if pnl_pct < self.worst_loss_pct:
                self.worst_loss_pct = pnl_pct

        # Feed back outcome to NumPy ML Model for Adaptive Online Learning!
        ml_loss = None
        if ENABLE_ONLINE_LEARNING and self.ml_engine is not None:
            # If price crashed > 30% or dev dumped -> actual label is RUG (True)
            # If price gained > 20% -> actual label is NOT RUG (False)
            is_rug_event = bool(pnl_pct < -20.0 or "DEV DUMP" in reason.upper() or "RUG" in reason.upper())
            ml_loss = self.ml_engine.train_step(pos.features, is_rug=is_rug_event)
            self.ml_engine.save_weights()

        record = {
            "mint": pos.mint,
            "symbol": pos.symbol,
            "entry_price": pos.entry_price_sol,
            "exit_price": current_price_sol,
            "pnl_pct": pnl_pct,
            "pnl_sol": pnl_sol,
            "reason": reason,
            "hold_time_sec": round(time.time() - pos.entry_time, 1),
            "ml_loss": ml_loss
        }

        self.trade_history.append(record)
        del self.positions[mint]
        return record

    def update_position_price(self, mint: str, new_price_sol: float, real_sol_in_curve: Optional[float] = None) -> Optional[str]:
        """
        Update position with latest live price and check for TP / SL / Dev Dump triggers.
        Returns trigger reason string if an auto-exit is met, else None.
        """
        pos = self.positions.get(mint)
        if not pos or pos.is_closed:
            return None

        pos.current_price_sol = new_price_sol
        if new_price_sol > pos.highest_price_sol:
            pos.highest_price_sol = new_price_sol

        if pos.entry_price_sol > 0:
            pos.current_pnl_pct = ((new_price_sol - pos.entry_price_sol) / pos.entry_price_sol) * 100.0

        # 1. Dev Dump Check: Did curve real SOL drop below 0.05 SOL while we held?
        if real_sol_in_curve is not None and real_sol_in_curve < 0.02 and pos.initial_curve_sol > 0.1:
            return "DEV DUMP DETECTED"

        # 2. Take Profit Trigger
        if pos.current_pnl_pct >= TAKE_PROFIT_PCT:
            return f"TAKE PROFIT (+{pos.current_pnl_pct:.1f}%)"

        # 3. Stop Loss Trigger
        if pos.current_pnl_pct <= -STOP_LOSS_PCT:
            return f"STOP LOSS ({pos.current_pnl_pct:.1f}%)"

        return None

    def get_portfolio_summary(self, sol_usd: Optional[float] = None) -> Dict[str, Any]:
        """Get summary of paper trading wallet performance with SOL & USD metrics."""
        from price_feed import get_cached_sol_price
        sol_usd = sol_usd or get_cached_sol_price() or 110.0

        invested_sol = sum(p.entry_sol_amount for p in self.positions.values())
        unrealized_sol = 0.0
        for pos in self.positions.values():
            unrealized_sol += (pos.entry_sol_amount * (pos.current_pnl_pct / 100.0))

        positions_val_sol = max(invested_sol + unrealized_sol, 0.0)
        net_equity_sol = self.balance_sol + positions_val_sol

        base_bal = self.initial_balance if self.initial_balance > 0 else 10.0
        total_pnl_sol = net_equity_sol - base_bal
        total_pnl_pct = (total_pnl_sol / base_bal) * 100.0 if base_bal > 0 else 0.0

        total_pnl_usd = total_pnl_sol * sol_usd
        realized_pnl_usd = self.total_realized_pnl_sol * sol_usd
        unrealized_pnl_usd = unrealized_sol * sol_usd
        net_equity_usd = net_equity_sol * sol_usd
        balance_usd = self.balance_sol * sol_usd
        invested_usd = invested_sol * sol_usd

        win_rate = (self.wins / self.total_trades * 100.0) if self.total_trades > 0 else 0.0

        return {
            "mode": "PAPER",
            "sol_usd_price": sol_usd,
            "balance_sol": self.balance_sol,
            "balance_usd": balance_usd,
            "invested_sol": invested_sol,
            "invested_usd": invested_usd,
            "positions_value_sol": positions_val_sol,
            "positions_value_usd": positions_val_sol * sol_usd,
            "unrealized_pnl_sol": unrealized_sol,
            "unrealized_pnl_usd": unrealized_pnl_usd,
            "realized_pnl_sol": self.total_realized_pnl_sol,
            "realized_pnl_usd": realized_pnl_usd,
            "net_equity_sol": net_equity_sol,
            "net_equity_usd": net_equity_usd,
            "baseline_sol": base_bal,
            "baseline_usd": base_bal * sol_usd,
            "total_pnl_sol": total_pnl_sol,
            "total_pnl_usd": total_pnl_usd,
            "total_pnl_pct": total_pnl_pct,
            "open_positions_count": len(self.positions),
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": win_rate,
            "best_win_pct": self.best_win_pct,
            "worst_loss_pct": self.worst_loss_pct
        }
