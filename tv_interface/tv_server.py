import asyncio
import json
import struct

import websockets


class TVServer:
    """WebSocket server for streaming audio + events to TV browser."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: set[websockets.WebSocketServerProtocol] = set()

    async def _handler(self, ws: websockets.WebSocketServerProtocol):
        self.clients.add(ws)
        try:
            async for _ in ws:
                pass
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)

    async def broadcast_audio(self, pcm_bytes: bytes):
        """Send PCM chunk to all TVs. Prefix: b"A" + 4-byte length."""
        if not self.clients:
            return
        msg = b"A" + struct.pack(">I", len(pcm_bytes)) + pcm_bytes
        await asyncio.gather(
            *(c.send(msg) for c in self.clients.copy()),
            return_exceptions=True,
        )

    async def broadcast_event(self, event: str, data: dict | None = None):
        """Send JSON event: speaking_start, speaking_end, subtitle, etc."""
        if not self.clients:
            return
        payload = json.dumps({"event": event, "data": data or {}}, ensure_ascii=False)
        await asyncio.gather(
            *(c.send(payload) for c in self.clients.copy()),
            return_exceptions=True,
        )

    async def start(self):
        async with websockets.serve(self._handler, self.host, self.port):
            print(f"[TVServer] Listening on ws://{self.host}:{self.port}")
            await asyncio.Future()
