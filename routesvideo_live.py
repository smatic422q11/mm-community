from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import date, datetime, timedelta
import secrets
from typing import Any, Optional, Dict
from bson import ObjectId

router = APIRouter()

# --- Globale Video & Sektor Einstellungen ---
VIDEO_DEFAULT_PLAETZE_PRO_TISCH = 8
VIDEO_TIMEOUT_SEKUNDEN = 60
LIVE_DEFAULT_DAUER_MIN = 60
LIVE_SLOTS = {"vormittag", "nachmittag"}

SEKTOR_THEMEN = {
    "1": "Recht auf Gefühlsvorderung", "2": "Wie werde ich Mensch", "3": "Glaube an Friede",
    "4": "Programm für Bürgerliche Rechte", "5": "Moralische Pflicht und Verantwortung",
    "6": "Menschlichkeit Wiederherstellung", "7": "Kinderschutz-Pflicht-Elternrechte",
    "8": "Wahre Richtung und Kunst", "9": "LGBTQ und Kirche", "10": "Trend und Tradition",
    "11": "Religionsbekenntnis oder Selbstwahl", "12": "Gesundheitswesen und Verhalten",
    "13": "Arbeitswelt und Du", "14": "Mobbing am Arbeitsplatz", "15": "Jugendsprecher",
    "16": "Ratgeber für Pensionisten", "17": "Sozialgefallen und Widerkehr",
    "18": "Nachbarschaft und Gemeinschaft", "19": "Alleinerziehend", "20": "Die Brücke",
    "21": "Kapital und Verwaltung", "22": "Globale Verbundenheit",
}

class VideoRouterConfig:
    def __init__(self) -> None:
        self.database: Any = None
        self.ws_manager: Any = None
        self.module_service: Any = None
        self.utils_module: Any = None
        self.mail_service: Any = None

_video_config_instance = VideoRouterConfig()

def set_video_router_config(
    database: Any = None,
    ws_manager: Any = None,
    module_service_instance: Any = None,
    utils_module: Any = None,
    mail_service: Any = None,
) -> None:
    _video_config_instance.database = database
    _video_config_instance.ws_manager = ws_manager
    _video_config_instance.module_service = module_service_instance
    _video_config_instance.utils_module = utils_module
    _video_config_instance.mail_service = mail_service

def _get_db():
    """Die absolut saubere Architektur-Brücke zur Datenbank"""
    if _video_config_instance.database is not None:
        return _video_config_instance.database
    try:
        from database import database_service
        return database_service.get_db()
    except Exception:
        return None

# =====================================================================
# --- ECHTE HELFER-FUNKTIONEN (Rollen, Profil, Rechte) ---
# =====================================================================
ADMIN_EMAILS = {"mmcommunity22@gmail.com"}

def ist_admin(email: str) -> bool:
    return (email or "").lower().strip() in ADMIN_EMAILS

def profil_ist_verifiziert(rec: dict) -> bool:
    profil = (rec or {}).get("profil", {}) or {}
    return (
        bool(profil.get("vollstaendig"))
        and bool(profil.get("profilbild"))
        and bool((profil.get("vorname") or "").strip())
        and bool((profil.get("nachname") or "").strip())
    )

def bestimme_rolle(email: str) -> str:
    db = _get_db()
    email = (email or "").lower().strip()
    if ist_admin(email):
        return "admin"
    if db is not None:
        rec = db.codes.find_one({"email": email})
        if not rec:
            return "gast"
        if rec.get("abo_aktiv"):
            return "premium"
        if profil_ist_verifiziert(rec) or rec.get("admin_verifiziert"):
            return "verifiziert"
    return "basis"

def ist_premium(email: str) -> bool:
    return True  # Entwickler-Override, damit Tische immer sichtbar sind

def konto_ist_aktiv(email: str) -> bool:
    db = _get_db()
    email = (email or "").lower().strip()
    if ist_admin(email):
        return True
    if db is not None:
        rec = db.codes.find_one({"email": email})
        if not rec:
            return False
        if rec.get("konto_status") == "aktiv":
            return True
        return bool((rec.get("profil") or {}).get("vollstaendig"))
    return False

def _kurz_name(email: str) -> str:
    db = _get_db()
    if db is not None:
        rec = db.codes.find_one({"email": email}, {"profil": 1, "name": 1}) or {}
        p = rec.get("profil", {}) or {}
        return (f"{p.get('vorname','')} {p.get('nachname','')}".strip()
                or rec.get("name", "") or p.get("benutzername", "") or email.split("@")[0])
    return email.split("@")[0] if email else ""

def _email_zu_handle(email: str) -> str:
    db = _get_db()
    if db is not None:
        rec = db.codes.find_one({"email": email}, {"profil": 1}) or {}
        return (rec.get("profil", {}) or {}).get("benutzername", "")
    return ""

def _handle_zu_email(handle: str) -> str:
    db = _get_db()
    if db is not None:
        rec = db.codes.find_one({"profil.benutzername": (handle or "").strip()}, {"email": 1}) or {}
        return rec.get("email", "")
    return ""

def thema_fuer_user_gesperrt(sektor: int, email: str) -> bool:
    if ist_admin(email):
        return False
    return int(sektor) in {21, 22}

def zugang_verweigert_antwort():
    return JSONResponse(status_code=403, content={"success": False, "message": "Zugang verweigert."})

def rolle_gesperrt_antwort(rolle: str):
    return JSONResponse(status_code=403, content={"success": False, "message": f"Nur für {rolle} erlaubt."})

def _iso_date_string(val: Any) -> str:
    if not val:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)

# =====================================================================
# --- VIDEO & LIVE-RAUM LOGIK ---
# =====================================================================
def _video_config() -> dict:
    db = _get_db()
    if db is not None:
        cfg = db.system_config.find_one({"_id": "video"}) or {}
        return {"plaetze_pro_tisch": int(cfg.get("plaetze_pro_tisch", VIDEO_DEFAULT_PLAETZE_PRO_TISCH))}
    return {"plaetze_pro_tisch": VIDEO_DEFAULT_PLAETZE_PRO_TISCH}

def _live_regie_config() -> dict:
    db = _get_db()
    if db is not None:
        cfg = db.system_config.find_one({"_id": "live_regie"}) or {}
        return {"max_tische": int(cfg.get("max_tische", 0)), "pausiert": bool(cfg.get("pausiert", False))}
    return {"max_tische": 0, "pausiert": False}

def _prune_video_raum():
    db = _get_db()
    if db is not None:
        grenze = datetime.now().timestamp() - VIDEO_TIMEOUT_SEKUNDEN
        db.video_raum.delete_many({"last_seen_ts": {"$lt": grenze}})

def _anzahl_tische(count: int, plaetze: int, max_tische: int = 0) -> int:
    tische = 1
    while count >= plaetze * tische + 1:
        tische += 1
    if max_tische and max_tische > 0:
        tische = min(tische, max_tische)
    return tische

def _raum_neu_berechnen(raum: str, plaetze: int, max_tische: int = 0) -> dict:
    db = _get_db()
    if db is None:
        return {"teilnehmer": [], "anzahl_tische": 1, "count": 0, "warteliste": 0}
        
    teilnehmer = list(db.video_raum.find({"raum": raum}).sort("platz", 1))
    count = len(teilnehmer)
    tische = _anzahl_tische(count, plaetze, max_tische)
    sitzplaetze = tische * plaetze

    liste = []
    for i, t in enumerate(teilnehmer):
        if i < sitzplaetze:
            tisch = i // plaetze
            platz_am_tisch = i % plaetze
            status = "aktiv"
        else:
            tisch = -1
            platz_am_tisch = -1
            status = "warteliste"
        db.video_raum.update_one(
            {"_id": t["_id"]},
            {"$set": {"tisch": tisch, "platz_am_tisch": platz_am_tisch, "status": status}},
        )
        liste.append({
            "email": t.get("email"), "peer_id": t.get("peer_id"),
            "tisch": tisch, "platz_am_tisch": platz_am_tisch, "status": status,
        })

    warteliste = max(0, count - sitzplaetze)
    return {"teilnehmer": liste, "anzahl_tische": tische, "count": count, "warteliste": warteliste}

def _live_session_public(doc: dict, email: str = "", fuer_admin: bool = False) -> dict:
    email = (email or "").lower().strip()
    anmeldungen = doc.get("anmeldungen", []) or []
    meine = next((a for a in anmeldungen if isinstance(a, dict) and a.get("email") == email), None)
    
    start = doc.get("start")
    ende = doc.get("ende")
    jetzt = datetime.now()
    
    im_fenster = bool(isinstance(start, datetime) and isinstance(ende, datetime) and start <= jetzt <= ende)
    
    freigegeben = bool(doc.get("freigegeben"))
    angemeldet = meine is not None
    technik_ok = bool(meine and isinstance(meine, dict) and meine.get("technik_ok"))
    mein_status = (meine or {}).get("status", "") if isinstance(meine, dict) else ""
    freigabe_ok = freigegeben or mein_status == "freigegeben"
    
    betreten_frei = (
        doc.get("status") in ("offen", "live")
        and angemeldet
        and technik_ok
        and im_fenster
        and freigabe_ok
        and mein_status != "entfernt"
    )
    anzahl_technik = sum(1 for a in anmeldungen if isinstance(a, dict) and a.get("technik_ok"))

    ausgabe = {
        "session_id": str(doc.get("session_id", "")),
        "sektor": doc.get("sektor"),
        "thema": str(doc.get("thema", "")),
        "datum": str(doc.get("datum", "")),
        "slot": str(doc.get("slot", "")),
        "start": _iso_date_string(start),
        "ende": _iso_date_string(ende),
        "status": str(doc.get("status", "geplant")),
        "freigegeben": freigegeben,
        "max_teilnehmer": int(doc.get("max_teilnehmer", 7)),
        "anzahl_angemeldet": len(anmeldungen),
        "anzahl_technik_ok": anzahl_technik,
        "angemeldet": angemeldet,
        "technik_ok": technik_ok,
        "mein_status": mein_status,
        "im_fenster": im_fenster,
        "betreten_frei": betreten_frei,
    }
    
    if fuer_admin:
        ausgabe["anmeldungen"] = [
            {
                "email": a.get("email"),
                "handle": a.get("handle"),
                "technik_ok": bool(a.get("technik_ok")),
                "status": a.get("status", "angemeldet"),
                "angemeldet_am": _iso_date_string(a.get("angemeldet_am")),
            }
            for a in anmeldungen if isinstance(a, dict)
        ]
    return ausgabe

@router.get("/api/live/sessions")
async def live_sessions(email: str = "", sektor: str = ""):
    db = _get_db()
    if db is None:
        return JSONResponse(content={"success": False, "error": "Datenbank nicht verfügbar."}, status_code=500)
        
    email = (email or "").lower().strip()
    query = {"status": {"$ne": "beendet"}}
    
    if sektor and str(sektor).strip().lower() not in ("null", "undefined", ""):
        try:
            query["sektor"] = int(sektor)
        except ValueError:
            return JSONResponse(content={"success": False, "error": "Ungültiger Sektor-Parameter."}, status_code=400)
            
    docs = list(db.live_sessions.find(query).sort("start", 1))
    return {"success": True, "sessions": [_live_session_public(d, email) for d in docs]}

@router.post("/api/live/anmelden")
async def live_anmelden(request: Request):
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        session_id = (data.get("session_id") or "").strip()
        doc = db.live_sessions.find_one({"session_id": session_id})
        if not doc:
            return {"success": False, "error": "Zeitfenster nicht gefunden."}
        anmeldungen = doc.get("anmeldungen", []) or []
        if any(isinstance(a, dict) and a.get("email") == email for a in anmeldungen):
            return {"success": True, "bereits_angemeldet": True, "session": _live_session_public(doc, email)}
        if len(anmeldungen) >= int(doc.get("max_teilnehmer", 7)):
            return {"success": False, "voll": True, "error": "Dieses Zeitfenster ist ausgebucht."}
        rec = db.codes.find_one({"email": email}) or {}
        handle = ((rec.get("profil") or {}).get("benutzername")) or email.split("@")[0]
        jetzt = datetime.now()
        db.live_sessions.update_one(
            {"session_id": session_id},
            {"$push": {"anmeldungen": {
                "email": email, "handle": handle, "angemeldet_am": jetzt,
                "technik_ok": False, "technik_am": None, "status": "angemeldet",
            }}},
        )
        doc = db.live_sessions.find_one({"session_id": session_id})
        return {"success": True, "session": _live_session_public(doc, email)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/live/abmelden")
async def live_abmelden(request: Request):
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        session_id = (data.get("session_id") or "").strip()
        db.live_sessions.update_one(
            {"session_id": session_id},
            {"$pull": {"anmeldungen": {"email": email}}},
        )
        doc = db.live_sessions.find_one({"session_id": session_id})
        return {"success": True, "session": _live_session_public(doc, email) if doc else None}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/live/technik-check")
async def live_technik_check(request: Request):
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        session_id = (data.get("session_id") or "").strip()
        ok = bool(data.get("ok", True))
        res = db.live_sessions.update_one(
            {"session_id": session_id, "anmeldungen.email": email},
            {"$set": {"anmeldungen.$.technik_ok": ok, "anmeldungen.$.technik_am": datetime.now()}},
        )
        if not res.matched_count:
            return {"success": False, "error": "Du bist für dieses Zeitfenster nicht angemeldet."}
        doc = db.live_sessions.find_one({"session_id": session_id})
        return {"success": True, "session": _live_session_public(doc, email)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/live/status")
async def live_status(email: str = "", session_id: str = ""):
    db = _get_db()
    if db is None: return JSONResponse(status_code=500, content={"success": False})
    email = (email or "").lower().strip()
    doc = db.live_sessions.find_one({"session_id": (session_id or "").strip()})
    if not doc:
        return {"success": False, "error": "Zeitfenster nicht gefunden."}
    return {"success": True, "session": _live_session_public(doc, email)}

@router.get("/api/live/uebersicht")
async def live_uebersicht(email: str = ""):
    db = _get_db()
    email = (email or "").lower().strip()
    
    _prune_video_raum()
        
    heute = datetime.now().date().isoformat()
    regie = _live_regie_config()
    v_cfg = _video_config()
    plaetze = int(v_cfg.get("plaetze_pro_tisch", 8))

    sessions = []
    zaehler = {}
    
    if db is not None:
        try:
            docs = list(db.live_sessions.find({"datum": heute}).sort("start", 1))
            sessions = [_live_session_public(d, email) for d in docs]
            
            for t in db.video_raum.find({}, {"raum": 1}):
                r = str(t.get("raum", "?"))
                zaehler[r] = zaehler.get(r, 0) + 1
        except Exception as e:
            print(f"Fehler in live_uebersicht DB Abfrage: {e}")
            
    raeume = [
        {"sektor": r, "thema": SEKTOR_THEMEN.get(r, ""), "teilnehmer": n,
         "tische": _anzahl_tische(n, plaetze, regie.get("max_tische", 0))}
        for r, n in sorted(zaehler.items(), key=lambda x: (len(x[0]), x[0]))
    ]
    
    aktive_teilnehmer = sum(r["teilnehmer"] for r in raeume) if raeume else 0

    return {
        "success": True, 
        "heute": heute, 
        "pausiert": bool(regie.get("pausiert", False)),
        "sessions": sessions, 
        "raeume": raeume,
        "aktive_teilnehmer": aktive_teilnehmer
    }

@router.post("/api/video/join")
async def video_join(request: Request):
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        peer_id = (data.get("peer_id") or "").strip()
        try:
            raum = str(int(data.get("sektor") if data.get("sektor") is not None else data.get("raum")))
        except (TypeError, ValueError):
            return {"success": False, "error": "Ungültiges Thema (sektor)."}
        if not email or not peer_id:
            return {"success": False, "error": "email und peer_id erforderlich."}

        regie = _live_regie_config()
        _prune_video_raum()
        plaetze = _video_config().get("plaetze_pro_tisch", 8)
        jetzt = datetime.now()

        bestehend = db.video_raum.find_one({"email": email, "raum": raum})
        if bestehend:
            platz = int(bestehend.get("platz", 0))
        else:
            db.video_raum.delete_many({"email": email})
            belegte = sorted(int(d["platz"]) for d in db.video_raum.find({"raum": raum}, {"platz": 1}))
            platz = 0
            for p in belegte:
                if p == platz:
                    platz += 1
                else:
                    break

        db.video_raum.update_one(
            {"email": email, "raum": raum},
            {"$set": {
                "email": email, "raum": raum, "peer_id": peer_id, "platz": platz,
                "last_seen": jetzt, "last_seen_ts": jetzt.timestamp(),
            }},
            upsert=True,
        )

        info = _raum_neu_berechnen(raum, plaetze, regie.get("max_tische", 0))
        ich = db.video_raum.find_one({"email": email, "raum": raum}) or {}
        mein_tisch = int(ich.get("tisch", -1))
        andere = [
            {"email": t["email"], "peer_id": t["peer_id"], "tisch": t["tisch"], "platz_am_tisch": t["platz_am_tisch"]}
            for t in info["teilnehmer"]
            if t["email"] != email and t["status"] == "aktiv" and mein_tisch >= 0 and t["tisch"] == mein_tisch
        ]
        return {
            "success": True,
            "raum": raum,
            "tisch": mein_tisch,
            "platz_am_tisch": int(ich.get("platz_am_tisch", -1)),
            "status": ich.get("status", "warteliste"),
            "plaetze_pro_tisch": plaetze,
            "anzahl_tische": info["anzahl_tische"],
            "warteliste": info["warteliste"],
            "teilnehmer": info["teilnehmer"],
            "andere": andere,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/video/heartbeat")
async def video_heartbeat(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        try:
            raum = str(int(data.get("sektor") if data.get("sektor") is not None else data.get("raum")))
        except (TypeError, ValueError):
            raum = None
        jetzt = datetime.now()
        
        if email and raum and db is not None:
            db.video_raum.update_one(
                {"email": email, "raum": raum},
                {"$set": {"last_seen": jetzt, "last_seen_ts": jetzt.timestamp()}},
            )
            
        _prune_video_raum()
        plaetze = _video_config().get("plaetze_pro_tisch", 8)
        
        if not raum:
            return {"success": True, "teilnehmer": [], "plaetze_pro_tisch": plaetze, "anzahl_tische": 1, "warteliste": 0}
            
        info = _raum_neu_berechnen(raum, plaetze, _live_regie_config().get("max_tische", 0))
        return {
            "success": True,
            "raum": raum,
            "teilnehmer": info["teilnehmer"],
            "plaetze_pro_tisch": plaetze,
            "anzahl_tische": info["anzahl_tische"],
            "warteliste": info["warteliste"],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/video/leave")
async def video_leave(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if email and db is not None:
            db.video_raum.delete_many({"email": email})
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =====================================================================
# --- TISCH RESERVIERUNGEN & EINLADUNGEN ---
# =====================================================================
def _auto_validiere_reservierung(res: dict) -> dict:
    db = _get_db()
    if not res or res.get("status") != "geplant":
        return res
    if not ist_premium(res.get("ersteller_email", "")):
        return res
    eingeladene = res.get("eingeladene", []) or []
    if not eingeladene:
        return res
    if all(isinstance(g, dict) and g.get("status") == "angenommen" for g in eingeladene):
        if db is not None:
            db.tisch_reservierungen.update_one(
                {"_id": res["_id"]},
                {"$set": {"status": "live", "live_seit": datetime.now()}},
            )
        res["status"] = "live"
        res["live_seit"] = datetime.now()
    return res        

def _reservierung_public(res: dict, viewer_email: str = "", zeige_sensibel: bool = False) -> dict:
    if not res:
        return {}
    db = _get_db()
    viewer_email = (viewer_email or "").lower().strip()
    ist_ersteller = res.get("ersteller_email") == viewer_email
    darf_details = zeige_sensibel or ist_ersteller
    eingeladene = res.get("eingeladene", []) or []
    gaeste = []
    
    for g in eingeladene:
        if not isinstance(g, dict): continue
        online_check = False
        if db is not None:
            online_check = bool(db.video_raum.find_one({"email": g.get("email", ""), "raum": str(res.get("sektor"))}))
        eintrag = {
            "handle": g.get("handle", "") or _email_zu_handle(g.get("email", "")),
            "name": _kurz_name(g.get("email", "")),
            "status": g.get("status", "eingeladen"),
            "online": online_check,
        }
        if darf_details:
            eintrag["email"] = g.get("email", "")
        gaeste.append(eintrag)
        
    mein_status = next((g.get("status") for g in eingeladene if isinstance(g, dict) and g.get("email") == viewer_email), None)
    
    return {
        "id": str(res.get("_id")),
        "raum_id": res.get("raum_id", ""),
        "sektor": res.get("sektor"),
        "thema": res.get("thema", ""),
        "zeitpunkt": res.get("zeitpunkt", ""),
        "identitaet": res.get("identitaet", "") if darf_details else "",
        "status": res.get("status", "geplant"),
        "ersteller_name": _kurz_name(res.get("ersteller_email", "")),
        "ersteller_handle": _email_zu_handle(res.get("ersteller_email", "")),
        "ist_ersteller": ist_ersteller,
        "mein_status": mein_status,
        "eingeladene": gaeste,
        "angenommen": sum(1 for g in eingeladene if isinstance(g, dict) and g.get("status") == "angenommen"),
        "eingeladen_gesamt": len(eingeladene),
        "erstellt_am": _iso_date_string(res.get("erstellt_am")),
        "live_seit": _iso_date_string(res.get("live_seit")),
    }

@router.post("/api/tisch/reservieren")
async def tisch_reservieren(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        if not ist_premium(email):
            return rolle_gesperrt_antwort("premium")
            
        try:
            sektor = int(data.get("sektor"))
        except (TypeError, ValueError):
            return JSONResponse(status_code=400, content={"success": False, "message": "Ungültiges Thema."})
            
        if thema_fuer_user_gesperrt(sektor, email):
            return JSONResponse(status_code=403, content={"success": False, "message": "Dieses Thema hat keinen Live-Raum."})
            
        identitaet = (data.get("identitaet") or _kurz_name(email)).strip()[:120]
        zeitpunkt = (data.get("zeitpunkt") or "").strip()[:60]
        thema = (data.get("thema") or SEKTOR_THEMEN.get(str(sektor), "")).strip()[:160]
        
        doc = {
            "reservierungs_id": "res_" + secrets.token_hex(6),  
            "raum_id": "tr_" + secrets.token_hex(6),
            "ersteller_email": email,
            "sektor": sektor,
            "thema": thema,
            "zeitpunkt": zeitpunkt,
            "identitaet": identitaet,
            "status": "geplant",
            "eingeladene": [],
            "erstellt_am": datetime.now(),
        }
        
        if db is not None:
            res = db.tisch_reservierungen.insert_one(doc)
            doc["_id"] = res.inserted_id
            return {"success": True, "reservierung": _reservierung_public(doc, email)}
        return JSONResponse(status_code=500, content={"success": False, "message": "DB Fehler"})
    except Exception as e:
        print(f"Fehler bei /api/tisch/reservieren: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Reservierung fehlgeschlagen."})

@router.get("/api/tisch/meine")
async def tisch_meine(email: str = ""):
    db = _get_db()
    email = (email or "").lower().strip()
    
    if not konto_ist_aktiv(email):
        return zugang_verweigert_antwort()
        
    eigene, einladungen = [], []
    if db is not None:
        try:
            for r in db.tisch_reservierungen.find({"ersteller_email": email}).sort("erstellt_am", -1).limit(50):
                eigene.append(_reservierung_public(r, email))
            for r in db.tisch_reservierungen.find({"eingeladene.email": email}).sort("erstellt_am", -1).limit(50):
                einladungen.append(_reservierung_public(r, email))
        except Exception as e:
            print(f"Fehler bei /api/tisch/meine: {e}")
        
    return {"success": True, "rolle": bestimme_rolle(email), "darf_reservieren": ist_premium(email),
            "eigene": eigene, "einladungen": einladungen}

@router.post("/api/tisch/einladen")
async def tisch_einladen(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        if not ist_premium(email):
            return rolle_gesperrt_antwort("premium")
            
        res_id = data.get("reservierungs_id") or data.get("reservierung_id") or data.get("id")
        
        res = None
        if db is not None:
            try:
                obj_id = ObjectId(str(res_id).strip())
                res = db.tisch_reservierungen.find_one({"_id": obj_id})
            except Exception:
                pass  
            
        if not res:
            return JSONResponse(status_code=404, content={"success": False, "message": "Reservierung nicht gefunden."})
        if res.get("ersteller_email") != email:
            return JSONResponse(status_code=403, content={"success": False, "message": "Nur der Ersteller des Tisches darf einladen."})
            
        gast_ref = (data.get("gast_handle") or data.get("gast_ref") or "").strip()
        gast_email = (data.get("gast_email") or "").lower().strip()
        if gast_ref and not gast_email:
            gast_email = _handle_zu_email(gast_ref)
            
        if not gast_email or (db is not None and not db.codes.find_one({"email": gast_email})):
            return JSONResponse(status_code=404, content={"success": False, "message": "Mitglied nicht gefunden."})
        if gast_email == email:
            return JSONResponse(status_code=400, content={"success": False, "message": "Du sitzt bereits selbst am Tisch."})
            
        eingeladene = res.get("eingeladene", []) or []
        if any(isinstance(g, dict) and g.get("email") == gast_email for g in eingeladene):
            return JSONResponse(status_code=409, content={"success": False, "message": "Dieses Mitglied ist bereits eingeladen."})
        if len(eingeladene) >= 7:
            return JSONResponse(status_code=409, content={"success": False, "message": "Der Tisch ist voll (7+1)."})
            
        if db is not None:
            db.tisch_reservierungen.update_one(
                {"_id": res["_id"]},
                {"$push": {"eingeladene": {
                    "email": gast_email, "handle": _email_zu_handle(gast_email),
                    "status": "eingeladen", "eingeladen_am": datetime.now(),
                }}},
            )
            res = db.tisch_reservierungen.find_one({"_id": res["_id"]})
            
        return {"success": True, "reservierung": _reservierung_public(res, email)}
    except Exception as e:
        print(f"Fehler bei /api/tisch/einladen: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Einladung fehlgeschlagen."})

@router.post("/api/tisch/einladung/antwort")
async def tisch_einladung_antwort(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
            
        annehmen = bool(data.get("annehmen", True))
        res_id = data.get("reservierungs_id") or data.get("reservierung_id") or data.get("id")
        
        res = None
        if db is not None:
            try:
                obj_id = ObjectId(str(res_id).strip())
                res = db.tisch_reservierungen.find_one({"_id": obj_id})
            except Exception:
                pass  
            
        if not res:
            return JSONResponse(status_code=404, content={"success": False, "message": "Reservierung nicht gefunden."})
        if not any(isinstance(g, dict) and g.get("email") == email for g in (res.get("eingeladene", []) or [])):
            return JSONResponse(status_code=403, content={"success": False, "message": "Du bist an diesen Tisch nicht eingeladen."})
            
        if db is not None:
            db.tisch_reservierungen.update_one(
                {"_id": res["_id"], "eingeladene.email": email},
                {"$set": {"eingeladene.$.status": "angenommen" if annehmen else "abgelehnt"}},
            )
            res = db.tisch_reservierungen.find_one({"_id": res["_id"]})
            
        res = _auto_validiere_reservierung(res)
        return {"success": True, "reservierung": _reservierung_public(res, email), "live": res.get("status") == "live"}
    except Exception as e:
        print(f"Fehler bei /api/tisch/einladung/antwort: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Antwort fehlgeschlagen."})

@router.post("/api/tisch/live-freischalten")
async def tisch_live_freischalten(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        if not ist_premium(email):
            return rolle_gesperrt_antwort("premium")
            
        res_id = data.get("reservierungs_id") or data.get("reservierung_id") or data.get("id")
        
        res = None
        if db is not None:
            try:
                obj_id = ObjectId(str(res_id).strip())
                res = db.tisch_reservierungen.find_one({"_id": obj_id})
            except Exception:
                pass

        if not res or res.get("ersteller_email") != email:
            return JSONResponse(status_code=403, content={"success": False, "message": "Nur der Ersteller darf den Tisch live schalten oder Reservierung nicht gefunden."})
            
        if db is not None:
            db.tisch_reservierungen.update_one({"_id": res["_id"]}, {"$set": {"status": "live", "live_seit": datetime.now()}})
            res = db.tisch_reservierungen.find_one({"_id": res["_id"]})
            
        return {"success": True, "reservierung": _reservierung_public(res, email), "live": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})