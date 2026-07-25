from __future__ import annotations

from datetime import datetime
from typing import Any
import secrets
from bson import ObjectId

from fastapi import APIRouter, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from database import database_service
from modules import (
    ANZAHL_THEMEN_GESAMT, ki_aktiv_fuer_sektor, 
    thema_fuer_user_gesperrt, SEKTOR_THEMEN
)
from auth_routes import (
    konto_ist_aktiv, bestimme_rolle, zugang_verweigert_antwort
)
from utils import (
    darf_forum_nutzen, forum_gesperrt_antwort, ROLLE_POST_LIMIT, 
    posts_heute, autor_signatur, unsichtbarer_ki_scan
)
from ws_manager import manager as default_ws_manager

router = APIRouter(tags=["forum"])

class ForumRouterConfig:
    """Saubere DI-Konfiguration für den Forum-Router."""

    def __init__(self) -> None:
        self.database = None
        self.ws_manager = None
        self.module_service = None
        self.utils_module = None


_forum_config = ForumRouterConfig()


def set_forum_router_config(
    database: Any = None,
    ws_manager: Any = None,
    module_service_instance: Any = None,
    utils_module: Any = None,
) -> None:
    """Konfiguration injizieren, ohne Router untereinander zu koppeln."""
    _forum_config.database = database
    _forum_config.ws_manager = ws_manager
    _forum_config.module_service = module_service_instance
    _forum_config.utils_module = utils_module


def _get_db() -> Any:
    if _forum_config.database is not None:
        return _forum_config.database

    if database_service is not None:
        try:
            return database_service.get_db()
        except Exception:
            return None

    return None


def _get_ws_manager() -> Any:
    if _forum_config.ws_manager is not None:
        return _forum_config.ws_manager
    return default_ws_manager


# =====================================================================
# WEBSOCKET & FORUM ROUTEN
# =====================================================================

@router.websocket("/ws/forum/{beitrag_id}")
async def websocket_endpoint(websocket: WebSocket, beitrag_id: str):
    ws_manager = _get_ws_manager()
    await ws_manager.connect(websocket, beitrag_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, beitrag_id)

@router.post("/api/forum/post")
async def forum_post(request: Request, background_tasks: BackgroundTasks):
    try:
        db = _get_db()
        if db is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        if not darf_forum_nutzen(email):
            return forum_gesperrt_antwort()

        rolle = bestimme_rolle(email)
        tages_limit = ROLLE_POST_LIMIT().get(rolle, 1)
        if posts_heute(email) >= tages_limit:
            return JSONResponse(status_code=429, content={
                "success": False, "limit_erreicht": True, "rolle": rolle, "limit": tages_limit,
                "message": f"Dein Tageslimit ist erreicht ({tages_limit} Beitrag/Tag als {rolle}-Mitglied).",
            })

        try:
            sektor = int(data.get("sektor"))
        except (TypeError, ValueError):
            return JSONResponse(status_code=400, content={"success": False, "message": "Ungültiger Sektor."})
        if sektor < 1 or sektor > ANZAHL_THEMEN_GESAMT:
            return JSONResponse(status_code=400, content={"success": False, "message": "Unbekanntes Thema."})

        if thema_fuer_user_gesperrt(sektor, email):
            return JSONResponse(status_code=403, content={
                "success": False, "gesperrt": True,
                "message": "Dieses Thema wird gerade vorbereitet und ist noch nicht zum Posten freigeschaltet.",
            })

        text = (data.get("text") or "").strip()
        media = data.get("media") or ""
        media_typ = (data.get("media_typ") or "").strip().lower()
        ressource_url = (data.get("ressource_url") or "").strip()[:500]
        beitrag_typ = (data.get("beitrag_typ") or "gedanke").strip().lower()
        if beitrag_typ not in ("gedanke", "medien", "diskurs", "ressource"):
            beitrag_typ = "gedanke"
        sichtbarkeit = (data.get("sichtbarkeit") or "oeffentlich").strip().lower()
        if sichtbarkeit not in ("oeffentlich", "tisch-gruppe"):
            sichtbarkeit = "oeffentlich"
        reflektion = (data.get("reflektion") or "").strip()[:1000]
        profil_id = (data.get("profil_id") or "").strip()[:120]
        
        kommentare_erlauben = data.get("kommentare_erlauben", False)
        if isinstance(kommentare_erlauben, str):
            kommentare_erlauben = kommentare_erlauben.lower() in ('true', '1', 't', 'yes')

        if not text and not media and not ressource_url:
            return JSONResponse(status_code=400, content={"success": False, "message": "Leerer Beitrag."})
        if media and len(media) > 12_000_000:
            return JSONResponse(status_code=400, content={"success": False, "message": "Datei zu groß (kurzes Video/Bild)."})
        if media_typ not in ("bild", "video"):
            media_typ = "video" if media.startswith("data:video") else ("bild" if media else "")

        beitrag = autor_signatur(email)
        beitrag.update({
            "sektor": sektor,
            "beitrag_typ": beitrag_typ,
            "sichtbarkeit": sichtbarkeit,
            "text": text[:5000],
            "reflektion": reflektion,
            "media": media,
            "media_typ": media_typ,
            "ressource_url": ressource_url,
            "profil_id": profil_id,
            "kommentare": [],
            "kommentare_erlauben": kommentare_erlauben,
            "erstellt_am": datetime.now(),
        })
        ergebnis = db.forum_beitraege.insert_one(beitrag)

        if ki_aktiv_fuer_sektor(sektor):
            scan_text = text + (f"\n\nReflektion (Gefühlsvorderung): {reflektion}" if reflektion else "")
            background_tasks.add_task(
                unsichtbarer_ki_scan, str(ergebnis.inserted_id), sektor, email, scan_text
            )

        beitrag["_id"] = str(ergebnis.inserted_id)
        beitrag["erstellt_am"] = beitrag["erstellt_am"].isoformat()
        return {"success": True, "beitrag": beitrag}
    except Exception as e:
        print(f"Fehler bei /api/forum/post: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler im Stream."})

@router.post("/api/forum/kommentar")
async def forum_kommentar(request: Request):
    try:
        db = _get_db()
        if db is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        if not darf_forum_nutzen(email):
            return forum_gesperrt_antwort()

        beitrag_id = (data.get("beitrag_id") or "").strip()
        text = (data.get("text") or "").strip()
        if not beitrag_id or not text:
            return JSONResponse(status_code=400, content={"success": False, "message": "Kommentar leer."})
        try:
            oid = ObjectId(beitrag_id)
        except Exception:
            return JSONResponse(status_code=400, content={"success": False, "message": "Ungültiger Beitrag."})

        sig = autor_signatur(email)
        kommentar = {
            "kommentar_id": secrets.token_hex(8),
            "autor_name": sig["autor_name"],
            "autor_handle": sig["autor_handle"],
            "autor_bild": sig["autor_bild"],
            "autor_email": email,
            "text": text[:3000],
            "erstellt_am": datetime.now(),
        }
        res = db.forum_beitraege.update_one({"_id": oid}, {"$push": {"kommentare": kommentar}})
        if res.matched_count == 0:
            return JSONResponse(status_code=404, content={"success": False, "message": "Beitrag nicht gefunden."})
        
        ws_manager = _get_ws_manager()
        await ws_manager.broadcast(beitrag_id, {
            "type": "neuer_kommentar",
            "kommentar": {
                **kommentar,
                "erstellt_am": kommentar["erstellt_am"].isoformat()
            },
            "beitrag_id": beitrag_id
        })

        kommentar["erstellt_am"] = kommentar["erstellt_am"].isoformat()
        return {"success": True, "kommentar": kommentar}
    except Exception as e:
        print(f"Fehler bei /api/forum/kommentar: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler beim Kommentar."})

@router.get("/api/forum/posts")
async def forum_posts(email: str = "", sektor: str = "", limit: int = 100, typ: str = ""):
    db = _get_db()
    if db is None:
        return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

    email = (email or "").lower().strip()
    if not konto_ist_aktiv(email):
        return zugang_verweigert_antwort()
    if not darf_forum_nutzen(email):
        return forum_gesperrt_antwort()
    try:
        sektor_int = int(sektor)
    except (TypeError, ValueError):
        return JSONResponse(status_code=400, content={"success": False, "message": "Ungültiger Sektor."})

    gesperrt = thema_fuer_user_gesperrt(sektor_int, email)
    query = {"sektor": sektor_int}
    typ = (typ or "").strip().lower()
    if typ in ("gedanke", "medien", "diskurs", "ressource"):
        query["beitrag_typ"] = typ
    beitraege = []
    for b in db.forum_beitraege.find(query).sort("erstellt_am", -1).limit(max(1, min(int(limit), 300))):
        erstellt = b.get("erstellt_am")
        komm = []
        for k in (b.get("kommentare") or []):
            k_erstellt = k.get("erstellt_am")
            komm.append({
                "autor_name": k.get("autor_name", ""),
                "autor_handle": k.get("autor_handle", ""),
                "autor_bild": k.get("autor_bild", ""),
                "autor_email": k.get("autor_email", ""),
                "text": k.get("text", ""),
                "erstellt_am": k_erstellt.isoformat() if hasattr(k_erstellt, "isoformat") else str(k_erstellt),
                "eigener": k.get("autor_email") == email,
            })
        beitraege.append({
            "id": str(b.get("_id")),
            "sektor": b.get("sektor"),
            "beitrag_typ": b.get("beitrag_typ", "gedanke"),
            "sichtbarkeit": b.get("sichtbarkeit", "oeffentlich"),
            "autor_name": b.get("autor_name", ""),
            "autor_handle": b.get("autor_handle", ""),
            "autor_email": b.get("autor_email", ""),
            "autor_bild": b.get("autor_bild", ""),
            "text": b.get("text", ""),
            "reflektion": b.get("reflektion", ""),
            "media": b.get("media", ""),
            "media_typ": b.get("media_typ", ""),
            "ressource_url": b.get("ressource_url", ""),
            "kommentare_erlauben": b.get("kommentare_erlauben", True),
            "erstellt_am": erstellt.isoformat() if hasattr(erstellt, "isoformat") else str(erstellt),
            "eigener": b.get("autor_email") == email,
            "kommentare": komm,
        })
    return {
        "success": True, "sektor": sektor_int, "anzahl": len(beitraege),
        "gesperrt": gesperrt, "thema": SEKTOR_THEMEN.get(str(sektor_int), ""),
        "beitraege": beitraege,
    }