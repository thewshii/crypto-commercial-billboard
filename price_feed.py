"""
Real-time SOL/USD price feed with aggressive caching and multi-source fallback.
Sources:
1. Coinbase spot API (fast, reliable)
2. CoinGecko simple price API
"""

import time
import asyncio
import aiohttp
from typing import Optional

_CACHED_SOL_USD: float = 110.0
_LAST_FETCH_TIME: float = 0.0
_CACHE_TTL_SEC: float = 30.0


async def fetch_live_sol_price(session: Optional[aiohttp.ClientSession] = None) -> float:
    """Fetch live SOL price in USD with automatic failover."""
    global _CACHED_SOL_USD, _LAST_FETCH_TIME

    now = time.time()
    if now - _LAST_FETCH_TIME < _CACHE_TTL_SEC and _CACHED_SOL_USD > 0:
        return _CACHED_SOL_USD

    close_session = False
    if session is None or session.closed:
        session = aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"})
        close_session = True

    try:
        # Source 1: Coinbase Spot
        try:
            async with session.get(
                "https://api.coinbase.com/v2/prices/SOL-USD/spot",
                timeout=aiohttp.ClientTimeout(total=2.5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    amt = float(data.get("data", {}).get("amount", 0))
                    if amt > 0:
                        _CACHED_SOL_USD = amt
                        _LAST_FETCH_TIME = now
                        return _CACHED_SOL_USD
        except Exception:
            pass

        # Source 2: CoinGecko
        try:
            async with session.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
                timeout=aiohttp.ClientTimeout(total=2.5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    amt = float((data.get("solana") or {}).get("usd", 0))
                    if amt > 0:
                        _CACHED_SOL_USD = amt
                        _LAST_FETCH_TIME = now
                        return _CACHED_SOL_USD
        except Exception:
            pass

    finally:
        if close_session and not session.closed:
            await session.close()

    return _CACHED_SOL_USD


def get_cached_sol_price() -> float:
    """Synchronous getter for latest cached SOL/USD price."""
    return _CACHED_SOL_USD
