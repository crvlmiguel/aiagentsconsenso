"""Simple WebSocket manager for real-time inbox updates per tenant."""
from typing import Dict, Set
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, tenant_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(tenant_id, set()).add(ws)

    def disconnect(self, tenant_id: str, ws: WebSocket):
        if tenant_id in self.rooms:
            self.rooms[tenant_id].discard(ws)
            if not self.rooms[tenant_id]:
                del self.rooms[tenant_id]

    async def broadcast(self, tenant_id: str, payload: dict):
        dead = []
        for ws in self.rooms.get(tenant_id, set()):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)


manager = WSManager()
