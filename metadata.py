"""
Asynchronous IPFS metadata resolver for pump.fun tokens.
Extracts project socials (Twitter, Telegram, Website) and description.
"""

import asyncio
import aiohttp
from typing import Dict, Any
from config import IPFS_GATEWAYS


def extract_ipfs_cid(uri: str) -> str:
    """Extract IPFS CID or path from various IPFS URI formats."""
    if not uri:
        return ""
    uri = uri.strip()
    if "ipfs/" in uri:
        return uri.split("ipfs/")[-1]
    if uri.startswith("ipfs://"):
        return uri[7:]
    return uri


async def fetch_token_metadata(session: aiohttp.ClientSession, uri: str) -> Dict[str, Any]:
    """
    Fetch token metadata JSON from IPFS gateways with timeout and fallbacks.
    """
    cid = extract_ipfs_cid(uri)
    if not cid:
        return {}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    # If the original URI is already a full http link and not blocked ipfs.io, we can try it
    candidate_urls = []
    if uri.startswith("http") and "ipfs.io" not in uri:
        candidate_urls.append(uri)

    for gw in IPFS_GATEWAYS:
        candidate_urls.append(f"{gw}{cid}")

    for url in candidate_urls:
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict):
                        return {
                            "description": data.get("description", ""),
                            "twitter": data.get("twitter") or data.get("twitter_url"),
                            "telegram": data.get("telegram") or data.get("telegram_url"),
                            "website": data.get("website") or data.get("website_url"),
                            "image": data.get("image", "")
                        }
        except Exception:
            continue

    return {}
