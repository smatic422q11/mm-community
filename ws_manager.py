from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    """Zentraler WebSocket-Manager für Live-/Realtime-Funktionen."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, beitrag_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(beitrag_id, [])
        self.active_connections[beitrag_id].append(websocket)

    def disconnect(self, websocket: WebSocket, beitrag_id: str) -> None:
        if beitrag_id not in self.active_connections:
            return

        self.active_connections[beitrag_id] = [
            conn for conn in self.active_connections[beitrag_id] if conn is not websocket
        ]

        if not self.active_connections[beitrag_id]:
            del self.active_connections[beitrag_id]

    async def broadcast(self, beitrag_id: str, message: dict) -> None:
        if beitrag_id not in self.active_connections:
            return

        dead_connections: List[WebSocket] = []

        for connection in list(self.active_connections[beitrag_id]):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(connection, beitrag_id)


manager = ConnectionManager()