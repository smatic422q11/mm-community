from __future__ import annotations

import os
import re
import json
import zoneinfo
import requests
import math
from datetime import datetime, timedelta
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Dict, List, Any

from modules import (
    SECTOR_NAMES, SEKTOR_THEMEN, SECTOR_SOULS, M_UND_M_MODULE, 
    ANZAHL_THEMEN_GESAMT, GESPERRTE_THEMEN_FUER_USER,
    ki_aktiv_fuer_sektor, hole_seele, thema_fuer_user_gesperrt
)
from auth_routes import konto_ist_aktiv, bestimme_rolle, ist_admin, hat_aktives_abo

class UtilsRouterConfig:
    """Saubere DI-Konfiguration für das utils-Modul."""
    def __init__(self) -> None:
        self.database = None
        self.ws_manager = None
        self.module_service = None
        self.mail_service = None

_utils_config = UtilsRouterConfig()

def set_utils_module_config(
    database: Any = None,
    ws_manager: Any = None,
    module_service_instance: Any = None,
    mail_service: Any = None,
) -> None:
    """Konfiguration injizieren, ohne globale Database-Kopplung."""
    _utils_config.database = database
    _utils_config.ws_manager = ws_manager
    _utils_config.module_service = module_service_instance
    _utils_config.mail_service = mail_service

def _get_db():
    if _utils_config.database is not None:
        return _utils_config.database
    try:
        from database import database_service
        return database_service.get_db()
    except Exception:
        return None

# --- ZEIT & SUCHE ---
def ermittle_zeitgefuehl() -> str:
    try:
        zeitzone = zoneinfo.ZoneInfo("Europe/Berlin")
        jetzt = datetime.now(zeitzone)
        aktuelles_datum = jetzt.strftime("%d.%m.%Y")
        aktuelle_uhrzeit = jetzt.strftime("%H:%M")
        stunde = jetzt.hour
        if 5 <= stunde < 10:
            phase = "Morgen-Frequenz (Aktivierung)"
        elif 10 <= stunde < 14:
            phase = "Mittags-Frequenz (Fokus)"
        elif 14 <= stunde < 18:
            phase = "Nachmittags-Frequenz (Fluss)"
        elif 18 <= stunde < 22:
            phase = "Abend-Frequenz (Gefühlsforderung & Reflexion)"
        else:
            phase = "Nacht-Frequenz (Einschläfer-Agent aktiv / Unterbewusstseins-Scan)"
        return f"{aktuelles_datum} um {aktuelle_uhrzeit} Uhr [{phase}]"
    except Exception:
        return "Synchronisation läuft..."

def perform_google_search(query: str) -> str:
    api_key = os.getenv('GOOGLE_API_KEY')
    cx_id = os.getenv('GOOGLE_SEARCH_CX')
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx_id}&q={query}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json().get("items", [])
            if not results:
                return "HINWEIS: Keine aktuellen Medienberichte zu diesem Index auffindbar."
            such_berichte = []
            for item in results[:4]:
                titel = item.get("title", "Kein Titel")
                link = item.get("link", "Kein Link")
                beschreibung = item.get("snippet", "")
                such_berichte.append(f"QUELLE: {titel}\nLINK: {link}\nFAKTEN: {beschreibung}\n---")
            return "\n".join(such_berichte)
        return "HINWEIS: Schnittstelle liefert aktuell keine Rohdaten."
    except Exception as e:
        return f"Fehler bei der Suche: {str(e)}"

# --- WISSENSARCHIV & KI-SCANNER ---
def filtere_kollektiv_inhalt(roh_text: str) -> str:
    if not roh_text:
        return ""
    sauber = "".join(ch for ch in str(roh_text) if ch == "\n" or ch >= " ")
    sauber = " ".join(sauber.split())
    return sauber[:8000]

def speichere_kollektives_wissen(sector_id, inhalt: str, quelle_email: str, kategorie: str = "gesetzbuch") -> str:
    sauberer_inhalt = filtere_kollektiv_inhalt(inhalt)
    if not sauberer_inhalt:
        return ""
    
    database = _get_db()
    if database is None:
        return ""
        
    sektor_key = str(sector_id)
    database.mm_wissensarchiv.update_one(
        {"sector_id": sektor_key, "status": kategorie},
        {"$set": {
            "sector_id": sektor_key,
            "status": kategorie,
            "inhalt": sauberer_inhalt,
            "versiegelt": True,
            "quelle": quelle_email,
            "letztes_update": datetime.now(),
        }},
        upsert=True,
    )
    return sauberer_inhalt

def _cfg_doc(doc_id: str) -> dict:
    database = _get_db()
    if database is None:
        return {}
    return database.system_config.find_one({"_id": doc_id}) or {}

def hole_sektor_gesetz(sektor) -> str:
    try:
        doc = db.mm_wissensarchiv.find_one({"sector_id": str(sektor), "status": "gesetzbuch"}) or {}
        return (doc.get("inhalt") or "").strip()
    except Exception:
        return ""

def sektor_global_gesperrt(sektor) -> bool:
    cfg = _cfg_doc("sichtbarkeit")
    if cfg.get("global_offen") is False:
        return True
    return cfg.get("sektoren", {}).get(str(sektor)) == "gesperrt"

def _skip_scanner_fuer_sektor(sektor_int: int) -> bool:
    try:
        return int(sektor_int) in GESPERRTE_THEMEN_FUER_USER
    except (TypeError, ValueError):
        return True

def unsichtbarer_ki_scan(beitrag_id: str, sektor_int: int, email: str, roh_text: str) -> None:
    if _skip_scanner_fuer_sektor(sektor_int):
        return
    if not ki_aktiv_fuer_sektor(sektor_int):
        return
    if not roh_text or not roh_text.strip():
        return
    try:
        thema = SEKTOR_THEMEN.get(str(sektor_int), "Unbekannt")
        modul_handbuch = "\n".join(
            f"- {k} ({v['name']}): {v['frequenz']}" for k, v in M_UND_M_MODULE.items()
        )
        scan_prompt = (
            "Du bist ein unsichtbarer ethnografischer Analyst für ein Buchprojekt. "
            "Analysiere den folgenden Community-Beitrag NUR intern. Antworte AUSSCHLIESSLICH "
            "als kompaktes JSON, ohne Fließtext drumherum.\n\n"
            f"BRILLE 1 – SEKTOR-KONTEXT: Das Thema ist '{thema}'. Das emotionale Fundament der "
            "gesamten Plattform ist das 'Recht auf Gefühlsvorderung' (immer mit 'V').\n\n"
            f"BRILLE 2 – DIE 9 MODULE (A-I):\n{modul_handbuch}\n\n"
            f"BEITRAG:\n\"\"\"{roh_text[:4000]}\"\"\"\n\n"
            "Gib JSON zurück mit den Schlüsseln: "
            '{"sektor_essenz": "kurze ethnografische Essenz im Sektor-Kontext", '
            '"gefuehls_fundament": "Bezug zum Recht auf Gefühlsvorderung", '
            '"module": {"Modul_A": "...", "Modul_B": "...", "Modul_C": "...", "Modul_D": "...", '
            '"Modul_E": "...", "Modul_F": "...", "Modul_G": "...", "Modul_H": "...", "Modul_I": "..."}}'
        )
        api_key = os.getenv("GEMINI_API_KEY", "").strip().replace("[", "").replace("]", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        resp = requests.post(
            url,
            json={"contents": [{"role": "user", "parts": [{"text": scan_prompt}]}]},
            timeout=30,
        )
        auswertung_roh, sektor_essenz, gefuehls_fundament, modul_brille = "", "", "", {}
        res_data = resp.json()
        if resp.status_code == 200 and "candidates" in res_data:
            auswertung_roh = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            try:
                sauber = auswertung_roh.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(sauber)
                sektor_essenz = parsed.get("sektor_essenz", "")
                gefuehls_fundament = parsed.get("gefuehls_fundament", "")
                modul_brille = parsed.get("module", {}) or {}
            except Exception:
                sektor_essenz = auswertung_roh

        database = _get_db()
        if database is not None:
           database.mm_ethnografie_studie.insert_one({
            "beitrag_id": str(beitrag_id),
            "sektor": int(sektor_int),
            "thema": thema,
            "quelle_email": email,
            "roh_text": roh_text[:5000],
            "sektor_brille": sektor_essenz,
            "gefuehls_fundament": gefuehls_fundament,
            "modul_brille": modul_brille,
            "auswertung_roh": auswertung_roh,
            "versiegelt": True,
            "erstellt_am": datetime.now(),
        })
    except Exception as e:
        print(f"[SCANNER] Fehler: {e}")

# --- FOREN & HIERARCHIE ---
def ROLLE_POST_LIMIT():
    return {"gast": 0, "basis": 1, "verifiziert": 3, "premium": 999999, "admin": 999999}

def _heute_beginn() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

def posts_heute(email: str) -> int:
    try:
        database = _get_db()
        if database is None:
            return 0
        return database.forum_beitraege.count_documents(
            {"autor_email": (email or "").lower().strip(), "erstellt_am": {"$gte": _heute_beginn()}}
        )
    except Exception:
        return 0

def darf_profilsuche(email: str) -> bool:
    return bestimme_rolle(email) in ("verifiziert", "premium", "admin")

def ist_premium(email: str) -> bool:
    return bestimme_rolle(email) in ("premium", "admin")

def rolle_gesperrt_antwort(benoetigt: str):
    texte = {
        "verifiziert": "Diese Funktion ist erst für verifizierte Mitglieder verfügbar. Vervollständige dein Profil inklusive Profilbild, um freigeschaltet zu werden.",
        "premium": "Diese Funktion ist Premium-Mitgliedern vorbehalten (Tisch-Reservierung, Live-Sektor und Einladungen).",
    }
    return JSONResponse(
        status_code=403,
        content={"success": False, "zugang": "rolle_gesperrt", "benoetigt": benoetigt,
                 "message": texte.get(benoetigt, "Für diese Aktion fehlen dir die Rechte.")},
    )

def autor_signatur(email: str) -> dict:
    database = _get_db()
    if database is None:
        return {}
    rec = database.codes.find_one({"email": email}, {"profil": 1, "name": 1}) or {}
    profil = rec.get("profil", {}) or {}
    vorname = profil.get("vorname", "")
    nachname = profil.get("nachname", "")
    voller_name = (f"{vorname} {nachname}").strip() or rec.get("name") or email.split("@")[0]
    return {
        "autor_email": email,
        "autor_name": voller_name,
        "autor_handle": profil.get("benutzername", ""),
        "autor_bild": profil.get("profilbild", ""),
    }

def darf_forum_nutzen(email: str) -> bool:
    return konto_ist_aktiv(email)

def forum_gesperrt_antwort():
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "zugang": "kein_zertifikat",
            "message": "Kein Zugriff auf die Community. Schließe zuerst 'Recht auf Gefühlsvorderung' (Sektor 1) ab und erwirb dein Wahrheits-Zertifikat.",
        },
    )

# --- GEO & PRÄSENZ ---
STADT_KOORDINATEN = {
    "bregenz": (47.5031, 9.7471), "dornbirn": (47.4125, 9.7417), "feldkirch": (47.2382, 9.5992),
    "wien": (48.2082, 16.3738), "graz": (47.0707, 15.4395), "linz": (48.3069, 14.2858),
    "salzburg": (47.8095, 13.0550), "innsbruck": (47.2692, 11.4041), "klagenfurt": (46.6247, 14.3053),
    "berlin": (52.5200, 13.4050), "hamburg": (53.5511, 9.9937), "frankfurt": (50.1109, 8.6821),
    "muenchen": (48.1351, 11.5820), "münchen": (48.1351, 11.5820), "koeln": (50.9375, 6.9603), "köln": (50.9375, 6.9603),
    "stuttgart": (48.7758, 9.1829), "zuerich": (47.3769, 8.5417), "zürich": (47.3769, 8.5417), "bern": (46.9480, 7.4474),
    "mexiko-stadt": (19.4326, -99.1332), "mexico city": (19.4326, -99.1332), "ciudad de mexico": (19.4326, -99.1332),
    "guadalajara": (20.6597, -103.3496), "monterrey": (25.6866, -100.3161),
}
PRAESENZ_FENSTER_SEK = 300
NEU_FENSTER_TAGE = 14

def _stadt_coords(stadt):
    return STADT_KOORDINATEN.get((stadt or "").strip().lower())

def _distanz_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2 - la1)
    dl = math.radians(lo2 - lo1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))

def markiere_praesenz(email):
    email = (email or "").lower().strip()
    if not email:
        return
    try:
        database = _get_db()
        if database is not None:
            database.codes.update_one({"email": email}, {"$set": {"zuletzt_gesehen": datetime.now()}})
    except Exception:
        pass

def _ist_online(rec):
    ts = rec.get("zuletzt_gesehen")
    return isinstance(ts, datetime) and (datetime.now() - ts).total_seconds() <= PRAESENZ_FENSTER_SEK

def _ist_neu(rec):
    ts = rec.get("created_at")
    return isinstance(ts, datetime) and (datetime.now() - ts).days <= NEU_FENSTER_TAGE

# --- VIDEO & TISCH HILFEN ---
VIDEO_DEFAULT_PLAETZE_PRO_TISCH = 8
VIDEO_TIMEOUT_SEKUNDEN = 60

def _video_config() -> dict:
    database = _get_db()
    if database is None:
        return {"plaetze_pro_tisch": VIDEO_DEFAULT_PLAETZE_PRO_TISCH}
    cfg = database.system_config.find_one({"_id": "video"}) or {}
    return {"plaetze_pro_tisch": int(cfg.get("plaetze_pro_tisch", VIDEO_DEFAULT_PLAETZE_PRO_TISCH))}

def _live_regie_config() -> dict:
    database = _get_db()
    if database is None:
        return {"max_tische": 0, "pausiert": False}
    cfg = database.system_config.find_one({"_id": "live_regie"}) or {}
    return {"max_tische": int(cfg.get("max_tische", 0)), "pausiert": bool(cfg.get("pausiert", False))}

def _prune_video_raum():
    database = _get_db()
    if database is None:
        return
    grenze = datetime.now().timestamp() - VIDEO_TIMEOUT_SEKUNDEN
    database.video_raum.delete_many({"last_seen_ts": {"$lt": grenze}})

def _anzahl_tische(count: int, plaetze: int, max_tische: int = 0) -> int:
    tische = 1
    while count >= plaetze * tische + 2:
        tische += 1
    if max_tische and max_tische > 0:
        tische = min(tische, max_tische)
    return tische

def _raum_neu_berechnen(raum: str, plaetze: int, max_tische: int = 0) -> dict:
    database = _get_db()
    if database is None:
        return {"teilnehmer": [], "anzahl_tische": 1, "count": 0, "warteliste": 0}
        
    teilnehmer = list(database.video_raum.find({"raum": raum}).sort("platz", 1))
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
        database.video_raum.update_one(
            {"_id": t["_id"]},
            {"$set": {"tisch": tisch, "platz_am_tisch": platz_am_tisch, "status": status}},
        )
        liste.append({
            "email": t.get("email"), "peer_id": t.get("peer_id"),
            "tisch": tisch, "platz_am_tisch": platz_am_tisch, "status": status,
        })

    warteliste = max(0, count - sitzplaetze)
    return {"teilnehmer": liste, "anzahl_tische": tische, "count": count, "warteliste": warteliste}

def _live_raum_belegung(plaetze: int, max_tische: int) -> list:
    database = _get_db()
    if database is None:
        return []
    zaehler: Dict[str, int] = {}
    for t in database.video_raum.find({}, {"raum": 1}):
        r = str(t.get("raum", "?"))
        zaehler[r] = zaehler.get(r, 0) + 1
    return [
        {"sektor": r, "thema": SEKTOR_THEMEN.get(r, ""), "teilnehmer": n,
         "tische": _anzahl_tische(n, plaetze, max_tische)}
        for r, n in sorted(zaehler.items(), key=lambda x: (len(x[0]), x[0]))
    ]

def _kurz_name(email: str) -> str:
    database = _get_db()
    if database is None:
        return email.split("@")[0]
    rec = database.codes.find_one({"email": email}, {"profil": 1, "name": 1}) or {}
    p = rec.get("profil", {}) or {}
    return (f"{p.get('vorname','')} {p.get('nachname','')}".strip()
            or rec.get("name", "") or p.get("benutzername", "") or email.split("@")[0])

def _email_zu_handle(email: str) -> str:
    database = _get_db()
    if database is None:
        return ""
    rec = database.codes.find_one({"email": email}, {"profil": 1}) or {}
    return (rec.get("profil", {}) or {}).get("benutzername", "")

def _handle_zu_email(handle: str) -> str:
    database = _get_db()
    if database is None:
        return ""
    rec = database.codes.find_one({"profil.benutzername": (handle or "").strip()}, {"email": 1}) or {}
    return rec.get("email", "")

def hat_live_tisch_zugang(email: str, sektor: int) -> bool:
    email = (email or "").lower().strip()
    try:
        database = _get_db()
        if database is None:
            return False
        res = database.tisch_reservierungen.find_one({
            "sektor": int(sektor), "status": "live",
            "$or": [
                {"ersteller_email": email},
                {"eingeladene": {"$elemMatch": {"email": email, "status": "angenommen"}}},
            ],
        })
        return bool(res)
    except Exception:
        return False

def _auto_validiere_reservierung(res: dict) -> dict:
    if not res or res.get("status") != "geplant":
        return res
    if not ist_premium(res.get("ersteller_email", "")):
        return res
    eingeladene = res.get("eingeladene", []) or []
    if not eingeladene:
        return res
    if all(g.get("status") == "angenommen" for g in eingeladene):
        database = _get_db()
        if database is not None:
            database.tisch_reservierungen.update_one(
                {"_id": res["_id"]},
                {"$set": {"status": "live", "live_seit": datetime.now()}},
            )
        res["status"] = "live"
        res["live_seit"] = datetime.now()
    return res

def _reservierung_public(res: dict, viewer_email: str = "", zeige_sensibel: bool = False) -> dict:
    database = _get_db()
    viewer_email = (viewer_email or "").lower().strip()
    ist_ersteller = res.get("ersteller_email") == viewer_email
    darf_details = zeige_sensibel or ist_ersteller
    eingeladene = res.get("eingeladene", []) or []
    gaeste = []
    for g in eingeladene:
        online_check = False
        if database is not None:
            online_check = bool(database.video_raum.find_one({"email": g.get("email", ""), "raum": str(res.get("sektor"))}))
        eintrag = {
            "handle": g.get("handle", "") or _email_zu_handle(g.get("email", "")),
            "name": _kurz_name(g.get("email", "")),
            "status": g.get("status", "eingeladen"),
            "online": online_check,
        }
        if darf_details:
            eintrag["email"] = g.get("email", "")
        gaeste.append(eintrag)
    mein_status = None
    for g in eingeladene:
        if g.get("email") == viewer_email:
            mein_status = g.get("status")
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
        "angenommen": sum(1 for g in eingeladene if g.get("status") == "angenommen"),
        "eingeladen_gesamt": len(eingeladene),
        "erstellt_am": res.get("erstellt_am").isoformat() if hasattr(res.get("erstellt_am"), "isoformat") else "",
        "live_seit": res.get("live_seit").isoformat() if hasattr(res.get("live_seit"), "isoformat") else "",
    }

def _admin_guard(email: str):
    if not ist_admin(email):
        return JSONResponse(content={"success": False, "error": "Nicht autorisiert."}, status_code=403)
    return None

def _live_session_public(doc: dict, email: str = "", fuer_admin: bool = False) -> dict:
    email = (email or "").lower().strip()
    anmeldungen = doc.get("anmeldungen", []) or []
    meine = next((a for a in anmeldungen if a.get("email") == email), None)
    start = doc.get("start")
    ende = doc.get("ende")
    jetzt = datetime.now()
    im_fenster = bool(isinstance(start, datetime) and isinstance(ende, datetime) and start <= jetzt <= ende)
    freigegeben = bool(doc.get("freigegeben"))
    angemeldet = meine is not None
    technik_ok = bool(meine and meine.get("technik_ok"))
    mein_status = (meine or {}).get("status", "")
    freigabe_ok = freigegeben or mein_status == "freigegeben"
    betreten_frei = (
        doc.get("status") in ("offen", "live")
        and angemeldet
        and technik_ok
        and im_fenster
        and freigabe_ok
        and mein_status != "entfernt"
    )
    anzahl_technik = sum(1 for a in anmeldungen if a.get("technik_ok"))
    ausgabe = {
        "session_id": doc.get("session_id"),
        "sektor": doc.get("sektor"),
        "thema": doc.get("thema"),
        "datum": doc.get("datum"),
        "slot": doc.get("slot"),
        "start": start.isoformat() if isinstance(start, datetime) else start,
        "ende": ende.isoformat() if isinstance(ende, datetime) else ende,
        "status": doc.get("status", "geplant"),
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
                "angemeldet_am": a["angemeldet_am"].isoformat() if isinstance(a.get("angemeldet_am"), datetime) else a.get("angemeldet_am"),
            }
            for a in anmeldungen
        ]
    return ausgabe