"""
PumpPortal WebSocket Client for real-time Solana / pump.fun token launches.
Handles reconnection, heartbeats, and token creation event streaming.
"""

import asyncio
import json
import websockets
from typing import Callable, Awaitable, Optional
from config import PUMPPORTAL_WS_URL


class PumpPortalClient:
    def __init__(self, on_new_token: Callable[[dict], Awaitable[None]], ws_url: str = PUMPPORTAL_WS_URL):
        self.on_new_token = on_new_token
        self.ws_url = ws_url
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the WebSocket listener loop."""
        self.running = True
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self):
        """Stop the WebSocket listener."""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _listen_loop(self):
        retry_delay = 2
        while self.running:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5
                ) as ws:
                    # Subscribe to brand new token creation events
                    payload = {"method": "subscribeNewToken"}
                    await ws.send(json.dumps(payload))
                    retry_delay = 2  # Reset delay upon successful connection

                    while self.running:
                        try:
                            raw_msg = await ws.recv()
                            data = json.loads(raw_msg)

                            # Skip subscription acknowledgement messages
                            if "message" in data:
                                continue

                            # Verify that this is a token creation event
                            if "mint" in data:
                                # Process token via callback asynchronously
                                asyncio.create_task(self.on_new_token(data))

                        except websockets.ConnectionClosed:
                            break
                        except json.JSONDecodeError:
                            continue
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
