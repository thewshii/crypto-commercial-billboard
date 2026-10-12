"""
Asynchronous DexScreener API Client.
Fetches live pair data, liquidity, volume, transactions, and DexScreener paid boosts.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional
from config import DEXSCREENER_API_BASE, DEXSCREENER_ORDERS_BASE


class DexScreenerClient:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def get_token_data(self, mint: str) -> Dict[str, Any]:
        """
        Query DexScreener pairs and orders/boosts for a given token mint.
        """
        session = await self._get_session()
        result: Dict[str, Any] = {
            "has_pair": False,
            "dex_id": None,
            "pair_address": None,
            "price_usd": 0.0,
            "price_sol": 0.0,
            "liquidity_usd": 0.0,
            "fdv": 0.0,
            "volume_m5": 0.0,
            "txns_buys_m5": 0,
            "txns_sells_m5": 0,
            "boosts": 0,
            "twitter": None,
            "telegram": None,
            "website": None,
        }

        # 1. Fetch pair information
        pairs_url = f"{DEXSCREENER_API_BASE}/tokens/{mint}"
        try:
            async with session.get(pairs_url, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    pairs = data.get("pairs") or []
                    if pairs:
                        # Pick highest liquidity pair
                        best_pair = max(
                            pairs,
                            key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0.0)
                        )
                        result["has_pair"] = True
                        result["dex_id"] = best_pair.get("dexId")
                        result["pair_address"] = best_pair.get("pairAddress")
                        result["price_usd"] = float(best_pair.get("priceUsd") or 0.0)
                        result["price_sol"] = float(best_pair.get("priceNative") or 0.0)
                        result["fdv"] = float(best_pair.get("fdv") or 0.0)

                        liq = best_pair.get("liquidity") or {}
                        result["liquidity_usd"] = float(liq.get("usd") or 0.0)

                        vol = best_pair.get("volume") or {}
                        result["volume_m5"] = float(vol.get("m5") or 0.0)

                        txns = (best_pair.get("txns") or {}).get("m5") or {}
                        result["txns_buys_m5"] = int(txns.get("buys") or 0)
                        result["txns_sells_m5"] = int(txns.get("sells") or 0)

                        # Extract socials from DexScreener pair info
                        info = best_pair.get("info") or {}
                        for soc in info.get("socials") or []:
                            stype = soc.get("type", "").lower()
                            if "twitter" in stype or "x" in stype:
                                result["twitter"] = soc.get("url")
                            elif "telegram" in stype or "tg" in stype:
                                result["telegram"] = soc.get("url")
                        for web in info.get("websites") or []:
                            result["website"] = web.get("url")
        except Exception:
            pass

        # 2. Fetch DexScreener orders/boosts info
        orders_url = f"{DEXSCREENER_ORDERS_BASE}/{mint}"
        try:
            async with session.get(orders_url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                if resp.status == 200:
                    odata = await resp.json(content_type=None)
                    if isinstance(odata, list):
                        result["boosts"] = len(odata)
                    elif isinstance(odata, dict):
                        boosts_list = odata.get("boosts") or []
                        orders_list = odata.get("orders") or []
                        result["boosts"] = len(boosts_list) + len(orders_list)
        except Exception:
            pass

        return result

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
