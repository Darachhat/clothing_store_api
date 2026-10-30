"""Real-time Barcode Scanner Pairing & Relay API for PC-Phone wireless scanning."""
from __future__ import annotations

import asyncio
import io
import json
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set

import qrcode
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/scanner", tags=["Barcode Scanner"])


@router.get("/qr", summary="Generate QR Code image for scanner pairing link")
async def generate_qr_code(text: str = Query(..., description="Text or URL to encode")):
    """Generate crisp PNG QR code image for instant phone camera pairing."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )



class ScanPayload(BaseModel):
    barcode: str
    format: Optional[str] = "UNKNOWN"
    device_info: Optional[str] = "Mobile Phone"


class SessionStatus(BaseModel):
    session_id: str
    phone_connected: bool
    pc_connected: bool
    scan_count: int
    last_barcode: Optional[str] = None


class ScannerManager:
    """Manages active scanner sessions and connected WebSockets."""

    def __init__(self) -> None:
        # session_id -> list of WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        # session_id -> metadata
        self.sessions: Dict[str, dict] = defaultdict(lambda: {
            "created_at": time.time(),
            "phone_connected": False,
            "pc_connected": False,
            "device_info": None,
            "scans": [],
            "last_barcode": None,
        })
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str, client_type: str) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections[session_id].add(websocket)
            if client_type == "phone":
                self.sessions[session_id]["phone_connected"] = True
            elif client_type == "pc":
                self.sessions[session_id]["pc_connected"] = True

        logger.info(f"Scanner WS: {client_type} joined session {session_id}")

        # Broadcast connection event to peers in this session
        await self.broadcast(
            session_id,
            {
                "type": "peer_connected",
                "client_type": client_type,
                "session_id": session_id,
                "phone_connected": self.sessions[session_id]["phone_connected"],
                "pc_connected": self.sessions[session_id]["pc_connected"],
            },
        )

    async def disconnect(self, websocket: WebSocket, session_id: str, client_type: str) -> None:
        async with self._lock:
            if session_id in self.active_connections:
                self.active_connections[session_id].discard(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]

            if client_type == "phone":
                self.sessions[session_id]["phone_connected"] = False
            elif client_type == "pc":
                self.sessions[session_id]["pc_connected"] = False

        logger.info(f"Scanner WS: {client_type} left session {session_id}")

        # Notify remaining peers
        await self.broadcast(
            session_id,
            {
                "type": "peer_disconnected",
                "client_type": client_type,
                "session_id": session_id,
                "phone_connected": self.sessions[session_id].get("phone_connected", False),
            },
        )

    async def broadcast(self, session_id: str, message: dict) -> None:
        connections = list(self.active_connections.get(session_id, set()))
        dead_sockets = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead_sockets.append(ws)

        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    self.active_connections[session_id].discard(ws)

    async def record_scan(self, session_id: str, barcode: str, format_name: str = "UNKNOWN", device: str = "") -> dict:
        scan_item = {
            "barcode": barcode.strip(),
            "format": format_name,
            "device": device,
            "timestamp": time.time(),
        }
        self.sessions[session_id]["scans"].append(scan_item)
        self.sessions[session_id]["last_barcode"] = barcode.strip()

        # Broadcast to all connected clients in this session
        await self.broadcast(
            session_id,
            {
                "type": "barcode_scanned",
                "barcode": barcode.strip(),
                "format": format_name,
                "timestamp": scan_item["timestamp"],
            },
        )
        return scan_item


manager = ScannerManager()


# ─── WebSocket Endpoint ───────────────────────────────────────────────────────
@router.websocket("/ws/{session_id}")
async def scanner_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time pairing and barcode relay.
    Query param or initial handshake can specify client_type ('pc' or 'phone').
    """
    client_type = websocket.query_params.get("client_type", "pc")
    await manager.connect(websocket, session_id, client_type)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
                msg_type = data.get("type")

                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif msg_type == "scan":
                    barcode = str(data.get("barcode", "")).strip()
                    if barcode:
                        await manager.record_scan(
                            session_id=session_id,
                            barcode=barcode,
                            format_name=data.get("format", "UNKNOWN"),
                            device=data.get("device", "Phone Camera"),
                        )
                elif msg_type == "identify":
                    new_type = data.get("client_type", client_type)
                    if new_type != client_type:
                        client_type = new_type
                        if client_type == "phone":
                            manager.sessions[session_id]["phone_connected"] = True
                            await manager.broadcast(
                                session_id,
                                {
                                    "type": "peer_connected",
                                    "client_type": "phone",
                                    "phone_connected": True,
                                },
                            )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket, session_id, client_type)
    except Exception as e:
        logger.error(f"Scanner WS error on session {session_id}: {e}")
        await manager.disconnect(websocket, session_id, client_type)


# ─── REST Fallback Endpoints ──────────────────────────────────────────────────
@router.post("/{session_id}/scan", status_code=status.HTTP_200_OK)
async def post_scan(session_id: str, payload: ScanPayload):
    """HTTP fallback to submit a scanned barcode from mobile phone."""
    if not payload.barcode.strip():
        raise HTTPException(status_code=400, detail="Barcode cannot be empty")

    item = await manager.record_scan(
        session_id=session_id,
        barcode=payload.barcode,
        format_name=payload.format or "UNKNOWN",
        device=payload.device_info or "Mobile Phone",
    )
    return {"status": "success", "data": item}


@router.get("/{session_id}/status", response_model=SessionStatus)
async def get_session_status(session_id: str):
    """Check pairing status of a scanner session."""
    session_data = manager.sessions[session_id]
    return SessionStatus(
        session_id=session_id,
        phone_connected=session_data.get("phone_connected", False),
        pc_connected=session_data.get("pc_connected", False),
        scan_count=len(session_data.get("scans", [])),
        last_barcode=session_data.get("last_barcode"),
    )


@router.get("/{session_id}/latest")
async def get_latest_scans(session_id: str, limit: int = 10):
    """Retrieve recent scans for polling fallback."""
    scans = manager.sessions[session_id].get("scans", [])
    return {"scans": scans[-limit:], "total": len(scans)}
