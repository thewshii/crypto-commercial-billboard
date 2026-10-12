"""
Market Regime Guard for Solana Pump.fun Sniper Bot.
Monitors the bot's own scanned tape over a trailing 3-hour window.
Measures runner rate (+10% gain with $1k+ volume after 30m) and blocks new entries
when the market is dead (score < 0.75% or < 500 completed tokens).
Never touches exits, wallet, or signing.
"""

import os
import time
import json
import inspect
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import config


class RegimeGuard:
    """
    Market Regime Guard evaluating real-time market quality from scanned token tape.
    """

    def __init__(self, dex=None, onchain=None):
        self.dex = dex
        self.onchain = onchain

        # Configuration constants (read from config with defaults)
        self.window_hours: float = float(getattr(config, "REGIME_WINDOW_HOURS", 3))
        self.min_vol_usd: float = float(getattr(config, "REGIME_MIN_VOL_USD", 1000.0))
        self.stand_down_threshold: float = float(getattr(config, "REGIME_STAND_DOWN_THRESHOLD", 0.0075))
        self.min_tokens: int = int(getattr(config, "REGIME_MIN_TOKENS", 500))
        self.recompute_sec: int = int(getattr(config, "REGIME_RECOMPUTE_SEC", 900))
        self.tape_file: str = str(getattr(config, "REGIME_TAPE_FILE", "regime_tape.jsonl"))
        self.state_file: str = str(getattr(config, "REGIME_STATE_FILE", "regime_state.json"))
        self.sample_every: int = int(getattr(config, "REGIME_SAMPLE_EVERY", 3))
        self.enabled: bool = bool(getattr(config, "REGIME_GUARD_ENABLED", True))

        # Runtime state
        self.state: str = "STAND_DOWN"
        self.score: float = 0.0
        self.window_tokens: int = 0
        self._scan_count: int = 0
        self._no_baseline_count: int = 0
        self.baseline_order: str = "dex_first"  # or "bonding_curve_first"

        # Tape storage
        self.tape: List[Dict[str, Any]] = []
        self._tape_by_mint: Dict[str, Dict[str, Any]] = {}
        self._unflushed: List[Dict[str, Any]] = []
        self._running: bool = False

        # Load existing state & tape to survive restarts
        self._load_tape()
        self._load_state()

    def _load_tape(self):
        """Load existing tape from disk, keeping unique mints and latest outcomes."""
        if not os.path.exists(self.tape_file):
            return
        try:
            with open(self.tape_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    mint = entry.get("mint")
                    if not mint:
                        continue
                    if mint in self._tape_by_mint:
                        self._tape_by_mint[mint].update(entry)
                    else:
                        self._tape_by_mint[mint] = entry
                        self.tape.append(entry)
        except Exception:
            pass

    def _load_state(self):
        """Load cached regime state from disk if present."""
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.state = str(data.get("state", "STAND_DOWN"))
                self.score = float(data.get("score", 0.0))
                self.window_tokens = int(data.get("window_tokens", 0))
        except Exception:
            pass

    def _extract_bonding_price(self, mint: str, token_data: Dict[str, Any]) -> float:
        """Extract baseline price from token_data bonding curve reserves or sync state."""
        if not token_data:
            return 0.0
        if "price_sol" in token_data and float(token_data["price_sol"]) > 0:
            return float(token_data["price_sol"])
        v_tokens = float(token_data.get("vTokensInBondingCurve") or 0.0)
        v_sol = float(token_data.get("vSolInBondingCurve") or 0.0)
        if v_tokens > 0 and v_sol > 0:
            return float(v_sol / v_tokens)
        return 0.0

    def _add_tape_entry(self, mint: str, t_scan: float, price_scan: float, vol_scan: float):
        """Append or update tape entry in memory and staging buffer."""
        entry = {
            "mint": mint,
            "t_scan": t_scan,
            "price_scan": float(price_scan),
            "vol_scan": float(vol_scan)
        }
        if mint not in self._tape_by_mint:
            self._tape_by_mint[mint] = entry
            self.tape.append(entry)
            self._unflushed.append(entry)
        else:
            self._tape_by_mint[mint].update(entry)

    def _flush_tape(self):
        """Append unflushed in-memory buffer to tape file on disk."""
        if not self._unflushed:
            return
        try:
            with open(self.tape_file, "a", encoding="utf-8") as f:
                for entry in self._unflushed:
                    f.write(json.dumps(entry) + "\n")
            self._unflushed.clear()
        except Exception:
            pass

    def _save_tape_atomic(self):
        """Rewrite entire tape to disk crash-safely using temp file + os.replace."""
        try:
            tmp_path = f"{self.tape_file}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                for entry in self.tape:
                    f.write(json.dumps(entry) + "\n")
            os.replace(tmp_path, self.tape_file)
            self._unflushed.clear()
        except Exception:
            pass

    def _save_state_atomic(self, state_data: Dict[str, Any]):
        """Write regime_state.json crash-safely using temp file + os.replace."""
        try:
            tmp_path = f"{self.state_file}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)
            os.replace(tmp_path, self.state_file)
        except Exception:
            pass

    async def _async_resolve_baseline(self, mint: str, t_scan: float, vol_scan: float):
        """Asynchronously read on-chain bonding curve state if sync resolution had no price."""
        try:
            curve_key = self.onchain.derive_bonding_curve(mint) if hasattr(self.onchain, "derive_bonding_curve") else None
            c_state = await self.onchain.get_bonding_curve_state(curve_key, mint=mint)
            price_sol = float((c_state or {}).get("price_sol") or 0.0)
            if price_sol > 0:
                self._add_tape_entry(mint, t_scan, price_sol, vol_scan)
            else:
                self._no_baseline_count += 1
        except Exception:
            self._no_baseline_count += 1

    def record_scan(self, token_data: Dict[str, Any], dex_data: Optional[Dict[str, Any]] = None):
        """
        Record a sampled token scan into the regime tape.
        Fire-and-forget: never raises, never blocks the trading loop.
        """
        try:
            self._scan_count += 1
            if self._scan_count % self.sample_every != 0:
                return

            mint = str(token_data.get("mint", ""))
            if not mint:
                return

            dex_data = dex_data or {}
            t_scan = time.time()
            vol_scan = float(dex_data.get("volume_m5") or dex_data.get("volume_usd") or dex_data.get("volume") or dex_data.get("vol_scan") or 0.0)

            # Determine baseline price based on baseline_order
            if self.baseline_order == "bonding_curve_first":
                price_scan = self._extract_bonding_price(mint, token_data)
                if price_scan <= 0:
                    price_scan = float(dex_data.get("price_sol") or 0.0)
            else:
                price_scan = float(dex_data.get("price_sol") or 0.0)
                if price_scan <= 0:
                    price_scan = self._extract_bonding_price(mint, token_data)

            if price_scan > 0:
                self._add_tape_entry(mint, t_scan, price_scan, vol_scan)
                return

            # If still no baseline, check onchain client
            if self.onchain and hasattr(self.onchain, "get_bonding_curve_state"):
                fn = self.onchain.get_bonding_curve_state
                # Check if sync mock/client
                if not inspect.iscoroutinefunction(fn):
                    try:
                        curve_key = self.onchain.derive_bonding_curve(mint) if hasattr(self.onchain, "derive_bonding_curve") else None
                        c_state = fn(curve_key)
                        price_sol = float((c_state or {}).get("price_sol") or 0.0)
                        if price_sol > 0:
                            self._add_tape_entry(mint, t_scan, price_sol, vol_scan)
                            return
                    except Exception:
                        pass
                    self._no_baseline_count += 1
                    return
                else:
                    # Async onchain client
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._async_resolve_baseline(mint, t_scan, vol_scan))
                        return
                    except RuntimeError:
                        pass

            # No baseline available
            self._no_baseline_count += 1
        except Exception:
            pass

    async def _settle_step(self):
        """
        Take tape entries aged 30-40 min with no outcome (max 15 per cycle).
        Query DexScreener to determine if token became a runner or died.
        """
        now = time.time()
        # Find entries aged 30-40 min (1800s to 2400s) with no outcome
        candidates = [
            e for e in self.tape
            if e.get("outcome") is None and 1800 <= (now - e.get("t_scan", 0)) <= 2400
        ][:15]

        # Expired entries past 40 min without outcome are marked dead
        expired = [
            e for e in self.tape
            if e.get("outcome") is None and (now - e.get("t_scan", 0)) > 2400
        ]
        for exp in expired:
            exp["outcome"] = "dead"
            exp["return_30m"] = -1.0
            exp["t_settle"] = now

        if not candidates and not expired:
            return

        settled_any = bool(expired)
        for entry in candidates:
            mint = entry["mint"]
            price_scan = float(entry.get("price_scan", 0.0))
            try:
                data = await self.dex.get_token_data(mint) if self.dex else {}
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(60)
                    continue
                data = {}

            if isinstance(data, dict) and data.get("status") == 429:
                await asyncio.sleep(60)
                continue

            price_now = float((data or {}).get("price_sol") or 0.0)
            vol_now = float((data or {}).get("volume_m5") or (data or {}).get("volume_usd") or (data or {}).get("volume") or 0.0)

            if price_now > 0 and price_scan > 0:
                entry["return_30m"] = (price_now - price_scan) / price_scan
                entry["outcome"] = "settled"
                entry["price_30m"] = price_now
                entry["vol_30m"] = vol_now
            else:
                entry["return_30m"] = -1.0
                entry["outcome"] = "dead"
                entry["vol_30m"] = vol_now

            entry["t_settle"] = time.time()
            settled_any = True

        if settled_any:
            self._save_tape_atomic()

    async def settle_loop(self):
        """Settle loop executing settlement cycle every 60s."""
        while self._running:
            try:
                await self._settle_step()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(60)

    def recompute(self) -> Tuple[str, float, int]:
        """
        Recompute regime score from trailing REGIME_WINDOW_HOURS completed outcomes.
        Returns (state, score, window_tokens).
        """
        now = time.time()
        window_sec = self.window_hours * 3600
        cutoff = now - window_sec

        # Completed = outcomes with t_scan within trailing REGIME_WINDOW_HOURS
        completed = [
            e for e in self.tape
            if e.get("t_scan", 0) >= cutoff and e.get("outcome") in ("settled", "dead")
        ]
        n_completed = len(completed)

        # Count runners: return_30m > 0.10 and vol >= 1000
        runners = 0
        for e in completed:
            ret = float(e.get("return_30m", 0.0))
            vol = max(float(e.get("vol_scan", 0.0)), float(e.get("vol_30m", 0.0)))
            if e.get("outcome") == "settled" and ret > 0.10 and vol >= self.min_vol_usd:
                runners += 1

        score = (runners / n_completed) if n_completed > 0 else 0.0
        new_state = "STAND_DOWN" if (n_completed < self.min_tokens or score < self.stand_down_threshold) else "TRADE"

        # On state CHANGE: append to regime_log.txt and console.print loud line (no alarm sound)
        if new_state != self.state:
            iso_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            log_line = f"{iso_time} {new_state} score={score:.4f} n={n_completed}\n"
            try:
                with open("regime_log.txt", "a", encoding="utf-8") as f:
                    f.write(log_line)
            except Exception:
                pass

            try:
                from rich.console import Console
                Console().print(
                    f"[bold yellow]🛰️ REGIME CHANGE:[/bold yellow] [bold white]{self.state} ➔ {new_state}[/bold white] | "
                    f"Score: [bold cyan]{score*100:.2f}%[/bold cyan] | "
                    f"Window: [bold white]{n_completed} tokens/{int(self.window_hours)}h[/bold white]"
                )
            except Exception:
                print(f"🛰️ REGIME CHANGE: {self.state} -> {new_state} score={score:.4f} n={n_completed}")

            self.state = new_state

        self.score = score
        self.window_tokens = n_completed

        # Calculate no_baseline_rate
        total_scans = len(self.tape) + self._no_baseline_count
        no_baseline_rate = (self._no_baseline_count / total_scans) if total_scans > 0 else 0.0

        # Write regime_state.json crash-safely
        state_data = {
            "state": self.state,
            "score": round(self.score, 6),
            "window_tokens": self.window_tokens,
            "updated_at": now,
            "no_baseline_rate": round(no_baseline_rate, 4)
        }
        self._save_state_atomic(state_data)

        # Prune tape entries older than 7 days
        cutoff_7d = now - (7 * 86400)
        orig_count = len(self.tape)
        self.tape = [e for e in self.tape if e.get("t_scan", 0) >= cutoff_7d]
        if len(self.tape) < orig_count:
            self._tape_by_mint = {e["mint"]: e for e in self.tape if "mint" in e}
            self._save_tape_atomic()

        return self.state, self.score, self.window_tokens

    async def run(self):
        """
        Single background entry point.
        Executes settle_loop timing + recompute timing until cancelled.
        """
        self._running = True
        self.recompute()
        last_recompute = time.time()
        last_flush = time.time()

        while self._running:
            try:
                # 1. Run settlement step for tape entries aged 30-40 min
                await self._settle_step()

                # 2. Flush any unflushed scans every 60s
                now = time.time()
                if now - last_flush >= 60:
                    self._flush_tape()
                    last_flush = now

                # 3. Recompute score every REGIME_RECOMPUTE_SEC (900s)
                if now - last_recompute >= self.recompute_sec:
                    self.recompute()
                    last_recompute = now

                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self._flush_tape()
                break
            except Exception:
                await asyncio.sleep(60)

    def is_trade_allowed(self) -> bool:
        """True only if market regime allows trading."""
        return self.state == "TRADE"
