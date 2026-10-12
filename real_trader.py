"""
Real Solana Trading Engine using Helius RPC & PumpPortal Local Trading API.
Executes non-custodial live trades, signs transactions locally via Ed25519 (PyNaCl),
submits directly to Helius RPC, and monitors open positions for Take Profit / Stop Loss.
"""

import time
import asyncio
import base64
import json
import base58
import nacl.signing
import aiohttp
from typing import Dict, Any, Optional, List
import config


class RealPosition:
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
        p_rug: float,
        tx_hash: str
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
        self.tx_hash = tx_hash

        # Dynamic tracking
        self.highest_price_sol = entry_price_sol
        self.current_price_sol = entry_price_sol
        self.current_pnl_pct = 0.0
        self.is_closed = False
        self.close_reason = ""
        self.exit_tx_hash = ""
        self.realized_sol = 0.0


class RealTradingEngine:
    def __init__(
        self,
        private_key_b58: str = config.SOLANA_PRIVATE_KEY,
        helius_rpc_url: str = config.HELIUS_RPC_URL,
        session: Optional[aiohttp.ClientSession] = None
    ):
        self.helius_rpc_url = helius_rpc_url
        self._session = session
        self.positions: Dict[str, RealPosition] = {}
        self.trade_history: List[Dict[str, Any]] = []

        # Parse private key and initialize signer
        raw_key = base58.b58decode(private_key_b58.strip())
        self.signer = nacl.signing.SigningKey(raw_key[:32])
        self.pubkey = base58.b58encode(bytes(self.signer.verify_key)).decode("ascii")

        # Live wallet balance caching
        self.balance_sol = 0.0
        self.baseline_balance_sol = 0.0
        self.initial_balance = 0.0

        # Persistent Performance Stats
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.total_realized_pnl_sol = 0.0
        self.best_win_pct = 0.0
        self.worst_loss_pct = 0.0

        # Load persistent stats and positions
        self.load_stats()
        self.load_positions()

    def load_stats(self):
        """Load persistent portfolio baseline & stats from disk."""
        import os
        if os.path.exists("portfolio_stats.json"):
            try:
                with open("portfolio_stats.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.baseline_balance_sol = float(data.get("baseline_balance_sol", 0.0))
                self.total_realized_pnl_sol = float(data.get("total_realized_pnl_sol", 0.0))
                self.total_trades = int(data.get("total_trades", 0))
                self.wins = int(data.get("wins", 0))
                self.losses = int(data.get("losses", 0))
                self.best_win_pct = float(data.get("best_win_pct", 0.0))
                self.worst_loss_pct = float(data.get("worst_loss_pct", 0.0))
            except Exception:
                pass
        if os.path.exists("trade_history.json"):
            try:
                with open("trade_history.json", "r", encoding="utf-8") as f:
                    self.trade_history = json.load(f)
            except Exception:
                pass

    def save_stats(self):
        """Save persistent portfolio baseline & stats to disk."""
        try:
            data = {
                "baseline_balance_sol": self.baseline_balance_sol,
                "total_realized_pnl_sol": self.total_realized_pnl_sol,
                "total_trades": self.total_trades,
                "wins": self.wins,
                "losses": self.losses,
                "best_win_pct": self.best_win_pct,
                "worst_loss_pct": self.worst_loss_pct,
                "updated_at": time.time()
            }
            with open("portfolio_stats.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            with open("trade_history.json", "w", encoding="utf-8") as f:
                json.dump(self.trade_history[-100:], f, indent=2)
        except Exception:
            pass

    def save_positions(self):
        """Save open positions to disk so they persist across runs."""
        try:
            data = {}
            for mint, pos in self.positions.items():
                data[mint] = {
                    "mint": pos.mint,
                    "symbol": pos.symbol,
                    "name": pos.name,
                    "curve_key": pos.curve_key,
                    "entry_price_sol": pos.entry_price_sol,
                    "entry_sol_amount": pos.entry_sol_amount,
                    "tokens_amount": pos.tokens_amount,
                    "initial_curve_sol": pos.initial_curve_sol,
                    "features": pos.features,
                    "p_rug": pos.p_rug,
                    "tx_hash": pos.tx_hash,
                    "entry_time": pos.entry_time,
                    "highest_price_sol": pos.highest_price_sol,
                    "current_price_sol": pos.current_price_sol,
                    "current_pnl_pct": pos.current_pnl_pct
                }
            with open("open_positions.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_positions(self):
        """Load open positions from disk, auto-deriving bonding curves if missing."""
        import os
        from onchain import derive_bonding_curve
        if not os.path.exists("open_positions.json"):
            return
        try:
            with open("open_positions.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            for mint, p in data.items():
                curve_key = p.get("curve_key", "")
                if not curve_key:
                    curve_key = derive_bonding_curve(p["mint"]) or ""
                pos = RealPosition(
                    mint=p["mint"],
                    symbol=p.get("symbol", "TOKEN"),
                    name=p.get("name", "Unknown"),
                    curve_key=curve_key,
                    entry_price_sol=float(p.get("entry_price_sol", 0.0)),
                    entry_sol_amount=float(p.get("entry_sol_amount", 0.0)),
                    tokens_amount=float(p.get("tokens_amount", 0.0)),
                    initial_curve_sol=float(p.get("initial_curve_sol") if p.get("initial_curve_sol") is not None else 0.3),
                    features=p.get("features", []),
                    p_rug=float(p.get("p_rug", 0.0)),
                    tx_hash=p.get("tx_hash", "")
                )
                pos.entry_time = float(p.get("entry_time", time.time()))
                pos.highest_price_sol = float(p.get("highest_price_sol", pos.entry_price_sol))
                pos.current_price_sol = float(p.get("current_price_sol", pos.entry_price_sol))
                pos.current_pnl_pct = float(p.get("current_pnl_pct", 0.0))
                self.positions[mint] = pos
        except Exception:
            pass

    async def reconcile_positions(self) -> int:
        """
        Verify on-chain whether wallet actually holds tokens for loaded positions.
        Cleans up ghost positions that were already sold or dropped.
        """
        if not self.positions:
            return 0

        session = await self._get_session()
        owned_mints = {}
        for prog in [
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
        ]:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    self.pubkey,
                    {"programId": prog},
                    {"encoding": "jsonParsed"}
                ]
            }
            try:
                async with session.post(
                    self.helius_rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=5.0)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        accounts = (data.get("result") or {}).get("value", [])
                        for acc in accounts:
                            info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                            m = info.get("mint")
                            amt = float(info.get("tokenAmount", {}).get("uiAmount") or 0.0)
                            if m and amt > 0:
                                owned_mints[m] = amt
            except Exception:
                pass

        removed_count = 0
        for mint in list(self.positions.keys()):
            if mint not in owned_mints or owned_mints[mint] <= 0:
                del self.positions[mint]
                removed_count += 1

        if removed_count > 0:
            self.save_positions()
        return removed_count

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def refresh_balance(self) -> float:
        """Query real wallet balance from Helius RPC in SOL."""
        session = await self._get_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [self.pubkey]
        }
        try:
            async with session.post(
                self.helius_rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lamports = (data.get("result") or {}).get("value", 0)
                    self.balance_sol = lamports / 1e9
                    if self.baseline_balance_sol == 0.0:
                        deployed = sum(p.entry_sol_amount for p in self.positions.values())
                        self.baseline_balance_sol = self.balance_sol + deployed
                        self.save_stats()
                    if self.initial_balance == 0.0:
                        self.initial_balance = self.baseline_balance_sol
                    return self.balance_sol
        except Exception:
            pass
        return self.balance_sol

    def can_buy(self, buy_amount: float = config.DEFAULT_BUY_AMOUNT_SOL) -> bool:
        """Check if wallet has enough slots and balance (leaving reserve for fees)."""
        if not getattr(config, "YOLO_MODE", False):
            if len(self.positions) >= config.MAX_OPEN_POSITIONS:
                return False
        # In YOLO mode, buy all the way down to minimal gas reserve (0.003 SOL)
        min_reserve = 0.003 if getattr(config, "YOLO_MODE", False) else 0.005
        if self.balance_sol < (buy_amount + min_reserve):
            return False
        return True

    def _sign_and_encode_transaction(self, tx_bytes_raw: bytes) -> str:
        """
        Locally sign VersionedTransaction returned by PumpPortal.
        tx[0]: number of signatures (1)
        tx[1:65]: signature placeholder
        tx[65:]: VersionedMessage
        """
        tx_bytes = bytearray(tx_bytes_raw)
        message_bytes = bytes(tx_bytes[65:])
        sig = self.signer.sign(message_bytes).signature
        tx_bytes[1:65] = sig
        return base64.b64encode(bytes(tx_bytes)).decode("ascii")

    async def _broadcast_transaction(self, tx_b64: str) -> Optional[str]:
        """Broadcast signed transaction directly to Helius RPC."""
        session = await self._get_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                tx_b64,
                {
                    "encoding": "base64",
                    "skipPreflight": False,
                    "preflightCommitment": "processed",
                    "maxRetries": 3
                }
            ]
        }
        try:
            async with session.post(
                self.helius_rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=8.0)
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    print(f"⚠️ Helius sendTransaction Error: {data['error']}")
                    return None
                return data.get("result")
        except Exception as e:
            print(f"⚠️ Broadcast network error: {e}")
            return None

    async def confirm_transaction(self, tx_hash: str, max_timeout: float = 12.0) -> Optional[Dict[str, Any]]:
        """
        Poll Helius RPC until transaction is confirmed or finalized.
        Returns {'status': 'confirmed', 'meta': meta} or {'status': 'error', 'err': err} or None.
        """
        session = await self._get_session()
        start = time.time()
        payload_status = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignatureStatuses",
            "params": [[tx_hash], {"searchTransactionHistory": True}]
        }

        while (time.time() - start) < max_timeout:
            await asyncio.sleep(1.0)
            try:
                async with session.post(
                    self.helius_rpc_url,
                    json=payload_status,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=4.0)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        statuses = (data.get("result") or {}).get("value", [])
                        val = statuses[0] if statuses else None
                        if val is not None:
                            if val.get("err") is not None:
                                print(f"❌ Transaction {tx_hash[:16]} failed on-chain: {val['err']}")
                                return {"status": "error", "err": val["err"]}
                            conf = val.get("confirmationStatus")
                            if conf in ("confirmed", "finalized"):
                                # Fetch full transaction details to extract exact balance diff
                                p_tx = {
                                    "jsonrpc": "2.0",
                                    "id": 1,
                                    "method": "getTransaction",
                                    "params": [
                                        tx_hash,
                                        {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                                    ]
                                }
                                async with session.post(
                                    self.helius_rpc_url,
                                    json=p_tx,
                                    headers={"Content-Type": "application/json"},
                                    timeout=aiohttp.ClientTimeout(total=4.0)
                                ) as resp_tx:
                                    if resp_tx.status == 200:
                                        d_tx = await resp_tx.json()
                                        meta = (d_tx.get("result") or {}).get("meta")
                                        return {"status": "confirmed", "meta": meta}
                                return {"status": "confirmed", "meta": None}
            except Exception:
                pass
        return None

    async def get_token_balance(self, mint: str) -> float:
        """Query on-chain token balance owned by wallet for a specific mint."""
        session = await self._get_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                self.pubkey,
                {"mint": mint},
                {"encoding": "jsonParsed"}
            ]
        }
        try:
            async with session.post(
                self.helius_rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=4.0)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    accounts = (data.get("result") or {}).get("value", [])
                    total = 0.0
                    for acc in accounts:
                        info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                        amt = float(info.get("tokenAmount", {}).get("uiAmount") or 0.0)
                        total += amt
                    return total
        except Exception:
            pass
        return 0.0

    async def execute_real_buy(
        self,
        token_data: Dict[str, Any],
        p_rug: float,
        features: List[float],
        buy_amount: float = config.DEFAULT_BUY_AMOUNT_SOL
    ) -> Optional[RealPosition]:
        """
        Execute real live buy transaction on Solana bonding curve.
        Confirms inclusion before creating open position.
        """
        mint = token_data.get("mint")
        if not mint or mint in self.positions:
            return None

        # Refresh balance before buying
        await self.refresh_balance()
        if not self.can_buy(buy_amount):
            return None

        session = await self._get_session()

        # 1. Request transaction from PumpPortal trade-local
        payload = {
            "publicKey": self.pubkey,
            "action": "buy",
            "mint": mint,
            "amount": buy_amount,
            "denominatedInSol": "true",
            "slippage": config.SLIPPAGE_PCT,
            "priorityFee": config.PRIORITY_FEE_SOL,
            "pool": "pump"
        }

        tx_raw_bytes = None
        for pool_candidate in ["pump", "pump-amm"]:
            payload["pool"] = pool_candidate
            try:
                async with session.post(
                    config.PUMPPORTAL_TRADE_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=7.0)
                ) as resp:
                    if resp.status == 200:
                        tx_raw_bytes = await resp.read()
                        break
                    else:
                        err_text = await resp.text()
                        if "pump-amm" not in err_text:
                            print(f"⚠️ PumpPortal buy error: {err_text}")
                            break
            except Exception as e:
                print(f"⚠️ PumpPortal request error: {e}")
                break

        if not tx_raw_bytes or len(tx_raw_bytes) < 100:
            return None

        # 2. Sign transaction locally
        try:
            signed_b64 = self._sign_and_encode_transaction(tx_raw_bytes)
        except Exception as e:
            print(f"⚠️ Failed to sign transaction: {e}")
            return None

        # 3. Broadcast to Helius RPC
        tx_hash = await self._broadcast_transaction(signed_b64)
        if not tx_hash:
            return None

        # 4. Verify on-chain confirmation before adding position
        conf_res = await self.confirm_transaction(tx_hash, max_timeout=getattr(config, "CONFIRM_TIMEOUT_SEC", 12.0))
        if not conf_res or conf_res.get("status") != "confirmed":
            err_msg = conf_res.get("err") if conf_res else "timeout/dropped"
            print(f"⚠️ Buy unconfirmed or dropped for {token_data.get('symbol')}: {err_msg}")
            await self.refresh_balance()
            return None

        # 5. Extract actual tokens acquired and entry price
        v_tokens = float(token_data.get("vTokensInBondingCurve") or 1073000000.0)
        v_sol = float(token_data.get("vSolInBondingCurve") or 30.0)
        k = v_tokens * v_sol
        new_v_sol = v_sol + buy_amount
        new_v_tokens = k / new_v_sol if new_v_sol > 0 else v_tokens
        sim_tokens = max(v_tokens - new_v_tokens, 1.0)

        meta = conf_res.get("meta")
        actual_tokens = 0.0
        if meta:
            post_tokens = meta.get("postTokenBalances") or []
            for tb in post_tokens:
                if tb.get("owner") == self.pubkey and tb.get("mint") == mint:
                    actual_tokens = float((tb.get("uiTokenAmount") or {}).get("uiAmount") or 0.0)
                    break

        tokens_bought = actual_tokens if actual_tokens > 0 else sim_tokens
        entry_price = buy_amount / tokens_bought if tokens_bought > 0 else (v_sol / v_tokens)

        # Update cached balance
        await self.refresh_balance()

        curve_key = token_data.get("bondingCurveKey", "")
        if not curve_key:
            from onchain import derive_bonding_curve
            curve_key = derive_bonding_curve(mint) or ""

        raw_init_sol = token_data.get("solAmount") if token_data.get("solAmount") is not None else 0.3
        pos = RealPosition(
            mint=mint,
            symbol=token_data.get("symbol", "TOKEN"),
            name=token_data.get("name", "Unknown"),
            curve_key=curve_key,
            entry_price_sol=entry_price,
            entry_sol_amount=buy_amount,
            tokens_amount=tokens_bought,
            initial_curve_sol=float(raw_init_sol),
            features=features,
            p_rug=p_rug,
            tx_hash=tx_hash
        )

        self.positions[mint] = pos
        self.save_positions()
        return pos

    async def execute_real_sell(
        self,
        mint: str,
        reason: str,
        current_price_sol: float
    ) -> Optional[Dict[str, Any]]:
        """
        Execute real live sell transaction selling 100% of holdings for mint.
        Validates token ownership on-chain, waits for confirmed inclusion,
        and computes exact P&L from wallet lamport balance changes.
        """
        pos = self.positions.get(mint)
        if not pos or pos.is_closed:
            return None

        # Verify on-chain token balance before attempting to sell
        token_bal = await self.get_token_balance(mint)
        if token_bal <= 0:
            print(f"⚠️ Cannot sell {pos.symbol} ({mint[:8]}): Wallet holds 0 tokens on-chain.")
            del self.positions[mint]
            self.save_positions()
            return None

        session = await self._get_session()

        payload = {
            "publicKey": self.pubkey,
            "action": "sell",
            "mint": mint,
            "amount": "100%",
            "denominatedInSol": "false",
            "slippage": config.SLIPPAGE_PCT,
            "priorityFee": config.PRIORITY_FEE_SOL,
            "pool": "pump"
        }

        tx_raw_bytes = None
        for pool_candidate in ["pump", "pump-amm"]:
            payload["pool"] = pool_candidate
            try:
                async with session.post(
                    config.PUMPPORTAL_TRADE_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=7.0)
                ) as resp:
                    if resp.status == 200:
                        tx_raw_bytes = await resp.read()
                        break
                    else:
                        err_text = await resp.text()
                        if "pump-amm" not in err_text:
                            print(f"⚠️ PumpPortal sell error: {err_text}")
                            break
            except Exception as e:
                print(f"⚠️ PumpPortal sell request error: {e}")
                break

        if not tx_raw_bytes or len(tx_raw_bytes) < 100:
            return None

        # Sign and broadcast sell transaction
        try:
            signed_b64 = self._sign_and_encode_transaction(tx_raw_bytes)
            exit_tx = await self._broadcast_transaction(signed_b64)
        except Exception as e:
            print(f"⚠️ Sell broadcast error: {e}")
            exit_tx = None

        if not exit_tx:
            print(f"⚠️ Sell broadcast failed for {pos.symbol}")
            return None

        # Wait for on-chain confirmation from Helius RPC
        conf_result = await self.confirm_transaction(exit_tx, max_timeout=getattr(config, "CONFIRM_TIMEOUT_SEC", 12.0))
        if not conf_result or conf_result.get("status") != "confirmed":
            err_msg = conf_result.get("err") if conf_result else "timeout/dropped"
            print(f"⚠️ Sell transaction not confirmed for {pos.symbol}: {err_msg}")
            # Check if tokens are still held
            rem_bal = await self.get_token_balance(mint)
            if rem_bal <= 0:
                pos.is_closed = True
                pos.close_reason = f"{reason} (CONFIRM_FAILED_ZERO_BAL)"
                pos.exit_tx_hash = exit_tx
                del self.positions[mint]
                self.save_positions()
            return None

        # Confirmed on-chain! Calculate EXACT SOL received from transaction meta
        meta = conf_result.get("meta")
        if meta and "preBalances" in meta and "postBalances" in meta:
            pre = meta["preBalances"][0]
            post = meta["postBalances"][0]
            diff_sol = (post - pre) / 1e9
            fee_sol = meta.get("fee", 0) / 1e9
            sol_received = max(diff_sol + fee_sol, 0.0)
        else:
            pnl_pct_calc = ((current_price_sol - pos.entry_price_sol) / pos.entry_price_sol) * 100.0 if pos.entry_price_sol > 0 else 0.0
            sol_received = max(pos.entry_sol_amount * (1.0 + (pnl_pct_calc / 100.0)), 0.0)

        # Realized P&L strictly reflects real SOL returned
        pnl_sol = sol_received - pos.entry_sol_amount
        pnl_pct = ((sol_received - pos.entry_sol_amount) / pos.entry_sol_amount * 100.0) if pos.entry_sol_amount > 0 else 0.0

        pos.current_price_sol = current_price_sol
        pos.current_pnl_pct = pnl_pct
        pos.is_closed = True
        pos.close_reason = reason
        pos.exit_tx_hash = exit_tx
        pos.realized_sol = sol_received

        from price_feed import get_cached_sol_price
        sol_usd = get_cached_sol_price() or 110.0

        # Update stats with real on-chain numbers
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

        record = {
            "mint": pos.mint,
            "symbol": pos.symbol,
            "entry_price": pos.entry_price_sol,
            "exit_price": current_price_sol,
            "entry_sol_amount": pos.entry_sol_amount,
            "sol_received": sol_received,
            "pnl_pct": pnl_pct,
            "pnl_sol": pnl_sol,
            "pnl_usd": pnl_sol * sol_usd,
            "reason": reason,
            "hold_time_sec": round(time.time() - pos.entry_time, 1),
            "entry_tx_hash": pos.tx_hash,
            "exit_tx_hash": pos.exit_tx_hash,
            "ml_loss": None
        }

        self.trade_history.append(record)
        del self.positions[mint]
        self.save_positions()
        self.save_stats()

        # Refresh balance after sale
        await self.refresh_balance()
        return record

    def update_position_price(
        self,
        mint: str,
        new_price_sol: float,
        real_sol_in_curve: Optional[float] = None
    ) -> Optional[str]:
        """Check for Take Profit, Stop Loss, or Dev Dump exit conditions."""
        pos = self.positions.get(mint)
        if not pos or pos.is_closed:
            return None

        pos.current_price_sol = new_price_sol
        if new_price_sol > pos.highest_price_sol:
            pos.highest_price_sol = new_price_sol

        if pos.entry_price_sol > 0:
            pos.current_pnl_pct = ((new_price_sol - pos.entry_price_sol) / pos.entry_price_sol) * 100.0

        # Dev Dump Check
        if real_sol_in_curve is not None and real_sol_in_curve < 0.02 and pos.initial_curve_sol > 0.1:
            return "DEV DUMP DETECTED"

        # Take Profit Check
        if pos.current_pnl_pct >= config.TAKE_PROFIT_PCT:
            return f"TAKE PROFIT (+{pos.current_pnl_pct:.1f}%)"

        # Stop Loss Check
        if pos.current_pnl_pct <= -config.STOP_LOSS_PCT:
            return f"STOP LOSS ({pos.current_pnl_pct:.1f}%)"

        return None

    def get_portfolio_summary(self, sol_usd: Optional[float] = None) -> Dict[str, Any]:
        """Summary of live trading portfolio with rich SOL & USD metrics."""
        from price_feed import get_cached_sol_price
        sol_usd = sol_usd or get_cached_sol_price() or 110.0

        invested_sol = sum(p.entry_sol_amount for p in self.positions.values())
        unrealized_sol = 0.0
        for pos in self.positions.values():
            unrealized_sol += (pos.entry_sol_amount * (pos.current_pnl_pct / 100.0))

        positions_val_sol = max(invested_sol + unrealized_sol, 0.0)
        net_equity_sol = self.balance_sol + positions_val_sol

        base_bal = self.baseline_balance_sol if self.baseline_balance_sol > 0 else (self.initial_balance if self.initial_balance > 0 else 0.313256)
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
            "mode": "REAL",
            "pubkey": self.pubkey,
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
