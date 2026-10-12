"""
Solana On-Chain RPC Reader for Pump.fun Bonding Curves & Dev Wallet Profiling.
Reads live reserves, calculates real-time price in SOL, bonding curve progress,
and queries dev wallet transaction history via Helius RPC.
"""

import time
import base64
import struct
import hashlib
import base58
import aiohttp
from typing import Dict, Any, Optional
from config import SOLANA_RPC_ENDPOINTS

PUMP_PROGRAM_PUBKEY = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


def is_on_ed25519_curve(y_bytes: bytes) -> bool:
    """Check if 32-byte candidate point lies on the Ed25519 elliptic curve."""
    p = 2**255 - 19
    d = -121665 * pow(121666, p - 2, p) % p
    y = int.from_bytes(y_bytes, 'little') & ((1 << 255) - 1)
    if y >= p:
        return False
    u = (y * y - 1) % p
    v = (d * y * y + 1) % p
    inv_v = pow(v, p - 2, p)
    x2 = (u * inv_v) % p
    if x2 == 0:
        return True
    return pow(x2, (p - 1) // 2, p) == 1


def derive_bonding_curve(mint_b58: str) -> Optional[str]:
    """Derive deterministic pump.fun bonding curve PDA for any token mint."""
    if not mint_b58:
        return None
    try:
        mint_bytes = base58.b58decode(mint_b58)
        prog_bytes = base58.b58decode(PUMP_PROGRAM_PUBKEY)
        for bump in range(255, -1, -1):
            seed = b"bonding-curve" + mint_bytes + bytes([bump]) + prog_bytes + b"ProgramDerivedAddress"
            h = hashlib.sha256(seed).digest()
            if not is_on_ed25519_curve(h):
                return base58.b58encode(h).decode("ascii")
    except Exception:
        pass
    return None


class OnChainReader:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self.endpoints = SOLANA_RPC_ENDPOINTS

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def derive_bonding_curve(self, mint_b58: str) -> Optional[str]:
        return derive_bonding_curve(mint_b58)

    async def get_bonding_curve_state(
        self,
        bonding_curve_key: Optional[str] = None,
        mint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query Solana RPC for the pump.fun bonding curve account and unpack its binary struct.
        Auto-derives bonding_curve_key from mint if not provided.
        """
        if not bonding_curve_key and mint:
            bonding_curve_key = derive_bonding_curve(mint)

        if not bonding_curve_key:
            return None

        session = await self._get_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [
                bonding_curve_key,
                {"encoding": "base64"}
            ]
        }

        for endpoint in self.endpoints:
            try:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=2.5)
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    val = (data.get("result") or {}).get("value")
                    if not val:
                        continue

                    raw_b64 = val.get("data", [])[0]
                    raw_bytes = base64.b64decode(raw_b64)

                    if len(raw_bytes) < 49:
                        continue

                    # Pump.fun layout:
                    # 8-byte discriminator, then 5 uint64 fields (v_tokens, v_sol, r_tokens, r_sol, supply), 1 bool complete
                    disc, v_tokens, v_sol, r_tokens, r_sol, total_supply = struct.unpack('<8sQQQQQ', raw_bytes[:48])
                    complete = struct.unpack('<?', raw_bytes[48:49])[0]

                    v_tokens_norm = v_tokens / 1e6
                    v_sol_norm = v_sol / 1e9
                    r_sol_norm = r_sol / 1e9
                    r_tokens_norm = r_tokens / 1e6

                    price_sol = (v_sol_norm / v_tokens_norm) if v_tokens_norm > 0 else 0.0
                    curve_progress_pct = min((r_sol_norm / 85.0) * 100.0, 100.0)

                    return {
                        "curve_key": bonding_curve_key,
                        "price_sol": price_sol,
                        "v_tokens": v_tokens_norm,
                        "v_sol": v_sol_norm,
                        "real_sol": r_sol_norm,
                        "progress_pct": curve_progress_pct,
                        "is_complete": bool(complete),
                        "lamports": val.get("lamports", 0)
                    }
            except Exception:
                continue

        return None

    async def get_dev_wallet_stats(self, wallet_pubkey: str, page_cap: int = 5) -> Dict[str, Any]:
        """
        Query dev wallet transaction history to compute age in days and transaction count.
        Returns:
            {
                "has_data": bool,
                "txns": int,
                "age_days": float,
                "hit_page_cap": bool
            }
        """
        if not wallet_pubkey:
            return {"has_data": False}

        session = await self._get_session()
        total_txns = 0
        oldest_time = None
        before = None
        hit_page_cap = False

        endpoint = self.endpoints[0]  # Helius RPC endpoint is primary

        for page in range(page_cap):
            params = [wallet_pubkey, {"limit": 1000}]
            if before:
                params[1]["before"] = before

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": params
            }

            try:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=3.0)
                ) as resp:
                    if resp.status != 200:
                        break
                    data = await resp.json()
                    sigs = data.get("result") or []
                    if not sigs:
                        break
                    total_txns += len(sigs)
                    for s in sigs:
                        bt = s.get("blockTime")
                        if bt and (oldest_time is None or bt < oldest_time):
                            oldest_time = bt
                    before = sigs[-1].get("signature")
                    if len(sigs) < 1000:
                        break
                    if page == page_cap - 1 and len(sigs) == 1000:
                        hit_page_cap = True
            except Exception:
                if total_txns == 0:
                    return {"has_data": False}
                break

        if total_txns == 0 or oldest_time is None:
            return {"has_data": False}

        age_days = max((time.time() - oldest_time) / 86400.0, 0.0)
        return {
            "has_data": True,
            "txns": total_txns,
            "age_days": age_days,
            "hit_page_cap": hit_page_cap
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
