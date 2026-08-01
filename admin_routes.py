from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, FileResponse
from datetime import date, datetime, timedelta
import secrets
import os
import base64
from typing import Any, Optional, Dict
from bson import ObjectId
import re

router = APIRouter()

# --- Globale Admin Einstellungen ---
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

SECTOR_NAMES = {"1": "Seele 1"} # Fallbacks
GESPERRTE_THEMEN_FUER_USER = {21, 22}
ANZAHL_THEMEN_GESAMT = 22
LIVE_SLOTS = {"vormittag", "nachmittag"}
LIVE_DEFAULT_DAUER_MIN = 60
VIDEO_DEFAULT_PLAETZE_PRO_TISCH = 8

class AdminRouterConfig:
    def __init__(self) -> None:
        self.database: Any = None
        self.ws_manager: Any = None
        self.module_service: Any = None
        self.utils_module: Any = None
        self.mail_service: Any = None

_admin_config_instance = AdminRouterConfig()

def set_admin_router_config(
    database: Any = None,
    ws_manager: Any = None,
    module_service_instance: Any = None,
    utils_module: Any = None,
    mail_service: Any = None,
) -> None:
    _admin_config_instance.database = database
    _admin_config_instance.ws_manager = ws_manager
    _admin_config_instance.module_service = module_service_instance
    _admin_config_instance.utils_module = utils_module
    _admin_config_instance.mail_service = mail_service

def _get_db():
    """Die absolut saubere Architektur-Brücke zur Datenbank"""
    if _admin_config_instance.database is not None:
        return _admin_config_instance.database
    try:
        from database import database_service
        return database_service.get_db()
    except Exception:
        return None

ADMIN_EMAILS = {"mmcommunity22@gmail.com"}

def ist_admin(email: str) -> bool:
    return (email or "").lower().strip() in ADMIN_EMAILS

def _admin_guard(email: str):
    clean_email = (email or "").lower().strip()
    if not clean_email:
        return None  # Fallback für das Admin Panel im UI
    if not ist_admin(clean_email):
        return JSONResponse(content={"success": False, "error": "Nicht autorisiert."}, status_code=403)
    return None

def _iso_date_string(val: Any) -> str:
    if not val:
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)

# --- Autarke Admin-Helfer (Saubere Modul-Architektur) ---

def bestimme_rolle(email: str) -> str:
    db = _get_db()
    email = (email or "").lower().strip()
    if ist_admin(email): return "admin"
    if db is not None:
        rec = db.codes.find_one({"email": email})
        if not rec: return "gast"
        if rec.get("abo_aktiv"): return "premium"
        if rec.get("admin_verifiziert"): return "verifiziert"
    return "basis"

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
        grenze = datetime.now().timestamp() - 60
        db.video_raum.delete_many({"last_seen_ts": {"$lt": grenze}})

def _anzahl_tische(count: int, plaetze: int, max_tische: int = 0) -> int:
    tische = 1
    while count >= plaetze * tische + 1:
        tische += 1
    if max_tische and max_tische > 0:
        tische = min(tische, max_tische)
    return tische

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
    
    betreten_frei = (
        doc.get("status") in ("offen", "live")
        and angemeldet and technik_ok and im_fenster
        and (freigegeben or mein_status == "freigegeben")
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

def _reservierung_public(res: dict, viewer_email: str = "", zeige_sensibel: bool = False) -> dict:
    if not res: return {}
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

def filtere_kollektiv_inhalt(roh_text: str) -> str:
    if not roh_text: return ""
    sauber = "".join(ch for ch in str(roh_text) if ch == "\n" or ch >= " ")
    return " ".join(sauber.split())[:8000]

def speichere_kollektives_wissen(sector_id, inhalt: str, quelle_email: str, kategorie: str = "gesetzbuch") -> str:
    db = _get_db()
    if db is None: return ""
    sauberer_inhalt = filtere_kollektiv_inhalt(inhalt)
    if not sauberer_inhalt: return ""
    sektor_key = str(sector_id)
    db.mm_wissensarchiv.update_one(
        {"sector_id": sektor_key, "status": kategorie},
        {"$set": {
            "sector_id": sektor_key,
            "status": kategorie,
            "inhalt": sauberer_inhalt,
            "versiegelt": True,
            "quelle": quelle_email or "mmcommunity22@gmail.com",
            "letztes_update": datetime.now(),
        }},
        upsert=True,
    )
    return sauberer_inhalt

# =====================================================================
# ADMIN-ROUTEN
# =====================================================================

@router.get("/admin/stats")
async def admin_stats():
    try:
        db = _get_db()
        total = db.codes.count_documents({}) if db is not None else 0
        return {"success": True, "total_souls": total}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/update-sector")
async def admin_update_sector(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = data.get("email", "mmcommunity22@gmail.com").lower().strip()
        if not ist_admin(email):
            return JSONResponse(content={"success": False, "error": "Nicht autorisiert."}, status_code=403)

        try:
            sektor_key = str(int(data.get("sector_id")) + 1)
        except (TypeError, ValueError):
            return JSONResponse(content={"success": False, "error": "Ungültige Sektor-ID."}, status_code=400)

        status = (data.get("status") or "").strip()
        if status == "update-text":
            gespeichert = speichere_kollektives_wissen(sektor_key, data.get("header_text", ""), email, kategorie="gesetzbuch")
            if not gespeichert:
                return JSONResponse(content={"success": False, "error": "Kein verwertbarer Inhalt."}, status_code=400)
            return {"success": True, "gespeichert": True, "sector_id": sektor_key}

        if db is not None:
            db.mm_wissensarchiv.update_one(
                {"sector_id": sektor_key, "status": "gesetzbuch"},
                {"$set": {
                    "sector_id": sektor_key,
                    "fassaden_status": status,
                    "fassaden_update": datetime.now(),
                    "quelle": email,
                }},
                upsert=True,
            )
        return {"success": True, "fassaden_status": status, "sector_id": sektor_key}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/overview")
async def admin_overview(email: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        total = db.codes.count_documents({})
        admins = db.codes.count_documents({"role": "admin"})
        sektor_verteilung: Dict[str, int] = {}
        abgeschlossen_gesamt = 0
        for u in db.codes.find({}, {"aktueller_sektor": 1, "abgeschlossene_sektoren": 1}):
            sek = str(u.get("aktueller_sektor", "1"))
            sektor_verteilung[sek] = sektor_verteilung.get(sek, 0) + 1
            abgeschlossen_gesamt += len(u.get("abgeschlossene_sektoren", []) or [])
        aktive_video = db.video_raum.count_documents({})
        return {
            "success": True,
            "total_souls": total,
            "admins": admins,
            "sektor_verteilung": sektor_verteilung,
            "abgeschlossene_sektoren_gesamt": abgeschlossen_gesamt,
            "aktive_teilnehmer": aktive_video,
        }
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/users")
async def admin_users(email: str = "", suche: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        query = {}
        if suche:
            query = {"email": {"$regex": re.escape(suche.lower().strip()), "$options": "i"}}
        users = []
        for u in db.codes.find(query, {
            "email": 1, "role": 1, "aktueller_sektor": 1, "manifest_mode": 1,
            "aktuelles_modul": 1, "abgeschlossene_sektoren": 1, "created_at": 1,
            "abo_aktiv": 1, "admin_verifiziert": 1, "profil": 1,
        }).limit(500):
            u_email = u.get("email", "")
            users.append({
                "email": u_email,
                "role": u.get("role", "user"),
                "rolle": bestimme_rolle(u_email),
                "abo_aktiv": bool(u.get("abo_aktiv")),
                "aktueller_sektor": str(u.get("aktueller_sektor", "1")),
                "aktuelles_modul": u.get("manifest_mode") or u.get("aktuelles_modul") or "",
                "abgeschlossene_sektoren": u.get("abgeschlossene_sektoren", []) or [],
                "fortschritt": [],  # Dummy für Dashboard View
            })
        return {"success": True, "users": users, "anzahl": len(users)}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/set-user-progress")
async def admin_set_user_progress(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        guard = _admin_guard(data.get("email", "").lower().strip())
        if guard: return guard

        ziel = (data.get("ziel_email") or "").lower().strip()
        if not ziel: return JSONResponse(content={"success": False, "error": "ziel_email fehlt."}, status_code=400)

        set_data: dict = {"letztes_update": datetime.now().isoformat()}
        if data.get("aktueller_sektor") not in (None, ""):
            set_data["aktueller_sektor"] = str(data.get("aktueller_sektor"))
        if data.get("aktuelles_modul"):
            set_data["manifest_mode"] = data.get("aktuelles_modul")
            set_data["aktuelles_modul"] = data.get("aktuelles_modul")

        ziel_sektor = data.get("aktueller_sektor")
        if data.get("modul_freischalten") and ziel_sektor not in (None, ""):
            m_kurz = data.get("modul_freischalten")
            status_wert = data.get("modul_status") if data.get("modul_status") in ("Bereit", "Erfolgreich abgeschlossen") else "Bereit"
            set_data[f"module_status_sektor.{ziel_sektor}.{m_kurz}"] = status_wert
            set_data[f"module_status.{m_kurz}"] = status_wert

        if db is not None:
            db.codes.update_one({"email": ziel}, {"$set": set_data}, upsert=True)
            if data.get("sektor_abschliessen") and ziel_sektor not in (None, ""):
                db.codes.update_one(
                    {"email": ziel},
                    {"$addToSet": {"abgeschlossene_sektoren": str(ziel_sektor)}},
                    upsert=True,
                )
        return {"success": True, "fortschritt": []}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/send-certificate")
async def admin_send_certificate(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        guard = _admin_guard(data.get("email", "").lower().strip())
        if guard: return guard

        ziel = (data.get("ziel_email") or "").lower().strip()
        sektor_id = str(data.get("sector_id", "1"))
        if not ziel: return JSONResponse(content={"success": False, "error": "ziel_email fehlt."}, status_code=400)

        user_name = ziel.split('@')[0].capitalize()
        if db is not None:
            user_record = db.codes.find_one({"email": ziel}) or {}
            user_name = user_record.get("name") or user_name

        seelen_name = SECTOR_NAMES.get(sektor_id, "KI")
        letzter_scan = {"WAHRHAFTIGKEITS_SIEGEL": "Vom Administrator manuell ausgestelltes Wahrheits-Zertifikat."}
        
        # Nutzen der offiziellen Utils, falls vorhanden (Keine Lambdas)
        if _admin_config_instance.utils_module and hasattr(_admin_config_instance.utils_module, "generiere_wahrheits_zertifikat_pdf"):
            pdf_dateiname = _admin_config_instance.utils_module.generiere_wahrheits_zertifikat_pdf(ziel, user_name, sektor_id, letzter_scan)
        else:
            return JSONResponse(content={"success": False, "error": "Zertifikats-Modul nicht konfiguriert."}, status_code=500)

        versendet = False
        if _admin_config_instance.mail_service and hasattr(_admin_config_instance.mail_service, "send_email_with_attachment"):
            with open(pdf_dateiname, "rb") as attachment:
                encoded_pdf = base64.b64encode(attachment.read()).decode()
            versendet = _admin_config_instance.mail_service.send_email_with_attachment(
                to_email=ziel,
                subject=f"M&M Community – Dein Wahrheits-Zertifikat [Sektor {sektor_id} – {seelen_name}]",
                body=f"Anbei dein offiziell versiegeltes Wahrheits-Zertifikat fuer Sektor {sektor_id} ({seelen_name}).",
                attachment_name=f"Wahrheits_Zertifikat_Sektor_{sektor_id}.pdf",
                attachment_data=encoded_pdf,
            )
        return {"success": versendet, "ziel_email": ziel, "sector_id": sektor_id}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/ethnografie")
async def admin_ethnografie(email: str = "", sektor: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    try:
        db = _get_db()
        if db is None: return JSONResponse(status_code=500, content={"success": False})
        
        kapitel = []
        for s in range(1, ANZAHL_THEMEN_GESAMT + 1):
            if s in GESPERRTE_THEMEN_FUER_USER: continue
            anzahl = db.mm_ethnografie_studie.count_documents({"sektor": s})
            kapitel.append({"sektor": s, "thema": SEKTOR_THEMEN.get(str(s), ""), "anzahl": anzahl})

        detail = []
        if sektor not in (None, ""):
            try:
                s_int = int(sektor)
            except (TypeError, ValueError):
                s_int = None
            if s_int is not None:
                for d in db.mm_ethnografie_studie.find({"sektor": s_int}).sort("erstellt_am", -1).limit(200):
                    detail.append({
                        "sektor": d.get("sektor"),
                        "thema": d.get("thema", ""),
                        "sektor_brille": d.get("sektor_brille", ""),
                        "gefuehls_fundament": d.get("gefuehls_fundament", ""),
                        "modul_brille": d.get("modul_brille", {}) or {},
                        "roh_text": d.get("roh_text", ""),
                        "erstellt_am": _iso_date_string(d.get("erstellt_am")),
                    })
        return {
            "success": True,
            "kapitel": kapitel,
            "gesamt": db.mm_ethnografie_studie.count_documents({}),
            "detail": detail,
            "sektor": sektor,
        }
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/ethnografie/pdf")
async def admin_ethnografie_pdf(email: str = "", sektor: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    try:
        if _admin_config_instance.utils_module and hasattr(_admin_config_instance.utils_module, "generiere_ethnografie_buch_pdf"):
            pdf_dateiname = _admin_config_instance.utils_module.generiere_ethnografie_buch_pdf(
                nur_sektor=sektor if sektor not in (None, "") else None, 
                anonym=True
            )
            return FileResponse(pdf_dateiname, media_type="application/pdf", filename=pdf_dateiname)
        return JSONResponse(content={"success": False, "error": "PDF-Modul nicht geladen."}, status_code=500)
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/sektor-config")
async def admin_sektor_config(email: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    try:
        db = _get_db()
        ki_cfg = db.system_config.find_one({"_id": "sektor_ki"}) if db is not None else {}
        sicht_cfg = db.system_config.find_one({"_id": "sichtbarkeit"}) if db is not None else {}
        seelen_cfg = db.system_config.find_one({"_id": "sektor_seelen"}) if db is not None else {}
        
        ki_cfg = (ki_cfg or {}).get("sektoren", {})
        sicht_cfg = sicht_cfg or {}
        seelen_cfg = (seelen_cfg or {}).get("sektoren", {})
        
        sektoren = []
        for s in range(1, ANZAHL_THEMEN_GESAMT + 1):
            s_str = str(s)
            seele = seelen_cfg.get(s_str, {})
            name = seele.get("name", "Begleiter")
            wesen = seele.get("wesen", "")
            
            platzhalter = s in GESPERRTE_THEMEN_FUER_USER
            gesperrt = platzhalter or (sicht_cfg.get("sektoren", {}).get(s_str) == "gesperrt")
            sektoren.append({
                "sektor": s,
                "thema": SEKTOR_THEMEN.get(s_str, ""),
                "ki_verfuegbar": not platzhalter,
                "ki_aktiv": (not platzhalter) and bool(ki_cfg.get(s_str, True)),
                "seele_name": name,
                "seele_wesen": wesen,
                "sichtbarkeit": "gesperrt" if gesperrt else "sichtbar",
            })
        return {"success": True, "global_offen": sicht_cfg.get("global_offen", True), "sektoren": sektoren}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/sektor-config")
async def admin_sektor_config_set(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        guard = _admin_guard((data.get("email") or "").lower().strip())
        if guard: return guard

        if "global_offen" in data and db is not None:
            db.system_config.update_one(
                {"_id": "sichtbarkeit"},
                {"$set": {"global_offen": bool(data.get("global_offen"))}},
                upsert=True,
            )
            return {"success": True, "global_offen": bool(data.get("global_offen"))}

        try:
            s = str(int(data.get("sektor")))
        except (TypeError, ValueError):
            return JSONResponse(status_code=400, content={"success": False, "error": "Ungültiger Sektor."})

        if db is not None:
            if "ki_aktiv" in data:
                db.system_config.update_one({"_id": "sektor_ki"}, {"$set": {f"sektoren.{s}": bool(data.get("ki_aktiv"))}}, upsert=True)
            if "sichtbarkeit" in data:
                wert = "gesperrt" if data.get("sichtbarkeit") == "gesperrt" else "sichtbar"
                db.system_config.update_one({"_id": "sichtbarkeit"}, {"$set": {f"sektoren.{s}": wert}}, upsert=True)
                
            set_seele = {}
            if data.get("seele_name") is not None:
                set_seele[f"sektoren.{s}.name"] = (data.get("seele_name") or "").strip()[:80]
            if data.get("seele_wesen") is not None:
                set_seele[f"sektoren.{s}.wesen"] = (data.get("seele_wesen") or "").strip()[:1000]
            if set_seele:
                db.system_config.update_one({"_id": "sektor_seelen"}, {"$set": set_seele}, upsert=True)

        return {"success": True, "sektor": s}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/video-config")
async def admin_get_video_config(email: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    _prune_video_raum()
    cfg = _video_config()
    plaetze = cfg["plaetze_pro_tisch"]
    
    db = _get_db()
    teilnehmer = list(db.video_raum.find({}, {"_id": 0, "email": 1, "tisch": 1, "raum": 1, "status": 1})) if db is not None else []

    raeume: Dict[str, int] = {}
    for t in teilnehmer:
        r = str(t.get("raum", "?"))
        raeume[r] = raeume.get(r, 0) + 1
        
    tische_gesamt = sum(_anzahl_tische(n, plaetze) for n in raeume.values()) if raeume else 1
    raum_details = [
        {"raum": r, "thema": SEKTOR_THEMEN.get(r, ""), "teilnehmer": n, "tische": _anzahl_tische(n, plaetze)}
        for r, n in sorted(raeume.items(), key=lambda x: (len(x[0]), x[0]))
    ]
    return {
        "success": True,
        "plaetze_pro_tisch": plaetze,
        "anzahl_tische": tische_gesamt,
        "aktive_teilnehmer": len(teilnehmer),
        "teilnehmer": teilnehmer,
        "raeume": raum_details,
    }

@router.post("/admin/video-config")
async def admin_set_video_config(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        guard = _admin_guard(data.get("email", "").lower().strip())
        if guard: return guard
        plaetze = int(data.get("plaetze_pro_tisch", VIDEO_DEFAULT_PLAETZE_PRO_TISCH))
        plaetze = max(1, min(plaetze, 50))
        if db is not None:
            db.system_config.update_one(
                {"_id": "video"},
                {"$set": {"plaetze_pro_tisch": plaetze, "letztes_update": datetime.now()}},
                upsert=True,
            )
        return {"success": True, "plaetze_pro_tisch": plaetze}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/live-session/speichern")
async def admin_live_session_speichern(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        guard = _admin_guard(email)
        if guard: return guard
        try:
            sektor = int(data.get("sektor"))
        except (TypeError, ValueError):
            return {"success": False, "error": "Ungültiger Sektor."}
        slot = (data.get("slot") or "vormittag").strip().lower()
        if slot not in LIVE_SLOTS: slot = "vormittag"
        try:
            start = datetime.fromisoformat((data.get("start") or "").strip())
        except ValueError:
            return {"success": False, "error": "Ungültiger Startzeitpunkt (ISO-Format erwartet)."}
            
        dauer = int(data.get("dauer_min", LIVE_DEFAULT_DAUER_MIN))
        ende = start + timedelta(minutes=max(15, min(dauer, 180)))
        session_id = (data.get("session_id") or "").strip() or secrets.token_hex(8)
        thema = (data.get("thema") or SEKTOR_THEMEN.get(str(sektor), "")).strip()[:160]
        setz = {
            "sektor": sektor, "thema": thema, "slot": slot,
            "datum": start.date().isoformat(), "start": start, "ende": ende,
            "max_teilnehmer": max(1, min(int(data.get("max_teilnehmer", 7)), 7)),
            "status": (data.get("status") or "offen").strip().lower(),
            "freigegeben": bool(data.get("freigegeben", False)),
            "letztes_update": datetime.now(),
        }
        
        doc = None
        if db is not None:
            bestehend = db.live_sessions.find_one({"session_id": session_id})
            if bestehend:
                db.live_sessions.update_one({"session_id": session_id}, {"$set": setz})
            else:
                setz.update({"session_id": session_id, "anmeldungen": [],
                             "erstellt_am": datetime.now(), "erstellt_von": email})
                db.live_sessions.insert_one(setz)
            doc = db.live_sessions.find_one({"session_id": session_id})
            
        return {"success": True, "session": _live_session_public(doc, email) if doc else {}}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/live-sessions")
async def admin_live_sessions(email: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    db = _get_db()
    docs = list(db.live_sessions.find().sort("start", 1)) if db is not None else []
    return {"success": True, "sessions": [_live_session_public(d, email) for d in docs]}

@router.get("/admin/live-regie")
async def admin_live_regie(email: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    _prune_video_raum()
    db = _get_db()
    heute = datetime.now().date().isoformat()
    regie = _live_regie_config()
    plaetze = _video_config()["plaetze_pro_tisch"]
    docs = list(db.live_sessions.find({"datum": heute}).sort("start", 1)) if db is not None else []
    sessions = [_live_session_public(d, email, fuer_admin=True) for d in docs]
    
    zaehler = {}
    if db is not None:
        for t in db.video_raum.find({}, {"raum": 1}):
            r = str(t.get("raum", "?"))
            zaehler[r] = zaehler.get(r, 0) + 1
            
    raeume = [
        {"sektor": r, "thema": SEKTOR_THEMEN.get(r, ""), "teilnehmer": n,
         "tische": _anzahl_tische(n, plaetze, regie.get("max_tische", 0))}
        for r, n in sorted(zaehler.items(), key=lambda x: (len(x[0]), x[0]))
    ]
    return {"success": True, "heute": heute, "regie": regie, "sessions": sessions,
            "raeume": raeume, "aktive_teilnehmer": sum(r["teilnehmer"] for r in raeume)}

@router.post("/admin/live-regie/speichern")
async def admin_live_regie_speichern(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        guard = _admin_guard((data.get("email") or "").lower().strip())
        if guard: return guard
        max_tische = max(0, min(int(data.get("max_tische", 0)), 999))
        pausiert = bool(data.get("pausiert", False))
        if db is not None:
            db.system_config.update_one(
                {"_id": "live_regie"},
                {"$set": {"max_tische": max_tische, "pausiert": pausiert, "letztes_update": datetime.now()}},
                upsert=True,
            )
        return {"success": True, "regie": _live_regie_config()}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/live-session/teilnehmer")
async def admin_live_session_teilnehmer(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        admin_email = (data.get("email") or "").lower().strip()
        guard = _admin_guard(admin_email)
        if guard: return guard
        session_id = (data.get("session_id") or "").strip()
        ziel = (data.get("ziel_email") or "").lower().strip()
        aktion = (data.get("aktion") or "freigeben").strip().lower()
        status_map = {"freigeben": "freigegeben", "entfernen": "entfernt", "zuruecksetzen": "angemeldet"}
        neuer_status = status_map.get(aktion)
        if not session_id or not ziel or not neuer_status:
            return {"success": False, "error": "session_id, ziel_email und gültige aktion erforderlich."}
        
        doc = None
        if db is not None:
            res = db.live_sessions.update_one(
                {"session_id": session_id, "anmeldungen.email": ziel},
                {"$set": {"anmeldungen.$.status": neuer_status, "letztes_update": datetime.now()}},
            )
            if not res.matched_count:
                return {"success": False, "error": "Teilnehmer in diesem Zeitfenster nicht gefunden."}
            doc = db.live_sessions.find_one({"session_id": session_id})
            
        return {"success": True, "session": _live_session_public(doc, admin_email, fuer_admin=True) if doc else {}}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.post("/admin/set-mitglied-stufe")
async def admin_set_mitglied_stufe(request: Request):
    try:
        db = _get_db()
        data = await request.json()
        guard = _admin_guard((data.get("email") or "").lower().strip())
        if guard: return guard
        ziel = (data.get("ziel_email") or "").lower().strip()
        if not ziel: return {"success": False, "error": "ziel_email fehlt."}
        
        if db is not None:
            if not db.codes.find_one({"email": ziel}):
                return {"success": False, "error": "Mitglied nicht gefunden."}
                
            stufe = (data.get("stufe") or "").strip().lower()
            setz: dict = {"letztes_update": datetime.now()}
            if stufe == "premium":
                setz.update({"abo_aktiv": True})
            elif stufe == "verifiziert":
                setz.update({"abo_aktiv": False, "admin_verifiziert": True})
            elif stufe == "basis":
                setz.update({"abo_aktiv": False, "admin_verifiziert": False})
            else:
                if "premium" in data: setz["abo_aktiv"] = bool(data.get("premium"))
                if "verifiziert" in data: setz["admin_verifiziert"] = bool(data.get("verifiziert"))
                
            db.codes.update_one({"email": ziel}, {"$set": setz})
            rec = db.codes.find_one({"email": ziel}) or {}
            return {"success": True, "ziel_email": ziel, "rolle": bestimme_rolle(ziel), "abo_aktiv": bool(rec.get("abo_aktiv"))}
        return {"success": False, "error": "DB nicht erreichbar"}
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@router.get("/admin/reservierungen")
async def admin_reservierungen(email: str = ""):
    guard = _admin_guard(email)
    if guard: return guard
    _prune_video_raum()
    db = _get_db()
    liste = []
    try:
        if db is not None:
            for r in db.tisch_reservierungen.find({}).sort("erstellt_am", -1).limit(200):
                liste.append(_reservierung_public(r, email, zeige_sensibel=True))
    except Exception as e:
        print(f"Fehler bei /admin/reservierungen: {e}")
        
    zusammenfassung = {
        "gesamt": len(liste),
        "live": sum(1 for r in liste if r.get("status") == "live"),
        "geplant": sum(1 for r in liste if r.get("status") == "geplant"),
    }
    return {"success": True, "zusammenfassung": zusammenfassung, "reservierungen": liste}
