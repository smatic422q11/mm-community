from __future__ import annotations

import os
import re
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse  
from datetime import datetime
from typing import Any

from modules import (
    SEKTOR_THEMEN, 
    ANZAHL_THEMEN_GESAMT, 
    ki_aktiv_fuer_sektor, 
    hole_seele, 
    thema_fuer_user_gesperrt
)

from auth_routes import (
    konto_ist_aktiv, 
    bestimme_rolle, 
    zugang_verweigert_antwort, 
    hat_aktives_abo
)

from utils import (
    markiere_praesenz, 
    darf_profilsuche, 
    _stadt_coords, 
    _distanz_km, 
    _ist_online, 
    _ist_neu, 
    ROLLE_POST_LIMIT, 
    posts_heute, 
    _prune_video_raum, 
    _kurz_name, 
    hole_sektor_gesetz, 
    rolle_gesperrt_antwort, 
    ist_premium
)

class MiscRouterConfig:
    """Saubere DI-Konfiguration für das Misc/API-Modul."""
    def __init__(self) -> None:
        self.database = None
        self.ws_manager = None
        self.module_service = None
        self.mail_service = None

_misc_config = MiscRouterConfig()

def set_misc_router_config(
    database: Any = None,
    ws_manager: Any = None,
    module_service_instance: Any = None,
    mail_service: Any = None,
) -> None:
    """Konfiguration injizieren, ohne globale Database-Kopplung."""
    _misc_config.database = database
    _misc_config.ws_manager = ws_manager
    _misc_config.module_service = module_service_instance
    _misc_config.mail_service = mail_service

def _get_db():
    if _misc_config.database is not None:
        return _misc_config.database
    try:
        from database import database_service
        return database_service.get_db()
    except Exception:
        return None

router = APIRouter()

@router.post("/api/praesenz")
async def praesenz_ping(request: Request):
    try:
        data = await request.json()
        markiere_praesenz(data.get("email", ""))
    except Exception:
        pass
    return {"success": True}

@router.get("/api/profil/suche")
async def profil_suche(email: str = "", q: str = "", land: str = "", stadt: str = "",
                         umkreis: str = "land", status: str = "alle", buchstabe: str = "",
                         offset: int = 0, limit: int = 48):
    email = (email or "").lower().strip()
    if not konto_ist_aktiv(email):
        return zugang_verweigert_antwort()
    if not darf_profilsuche(email):
        return rolle_gesperrt_antwort("verifiziert")
    markiere_praesenz(email)

    database = _get_db()
    if database is None:
        return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

    begriff = (q or "").strip()
    gezielt = bool(begriff)
    try:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        limit, offset = 48, 0

    land_f = (land or "").strip().lower()
    stadt_f = (stadt or "").strip().lower()
    status = (status or "alle").strip().lower()
    buchstabe = (buchstabe or "").strip().upper()[:1]
    projektion = {"email": 1, "profil": 1, "created_at": 1, "zuletzt_gesehen": 1, "abo_aktiv": 1}

    treffer = []
    try:
        if gezielt:
            rx = {"$regex": re.escape(begriff), "$options": "i"}
            query = {"$or": [
                {"profil.benutzername": rx}, {"profil.vorname": rx}, {"profil.nachname": rx},
            ]}
            kandidaten = list(database.codes.find(query, projektion).limit(600))
        else:
            kandidaten = list(database.codes.find({"konto_status": "aktiv"}, projektion).limit(5000))

        km_radius = {"5": 5.0, "20": 20.0, "50": 50.0, "100": 100.0}.get(umkreis)
        zentrum = None
        if not gezielt and km_radius:
            eigen = (database.codes.find_one({"email": email}, {"profil": 1}) or {}).get("profil", {}) or {}
            zentrum = _stadt_coords(stadt) or _stadt_coords(eigen.get("stadt", ""))

        for rec in kandidaten:
            profil = rec.get("profil", {}) or {}
            handle = profil.get("benutzername", "") or ""
            vorname = profil.get("vorname", "") or ""
            nachname = profil.get("nachname", "") or ""
            p_land = (profil.get("land", "") or "").strip()
            p_stadt = (profil.get("stadt", "") or "").strip()
            voller_name = f"{vorname} {nachname}".strip()

            if not gezielt:
                if not profil.get("vollstaendig"):
                    continue
                if land_f and land_f not in p_land.lower():
                    continue
                if km_radius and zentrum:
                    coords = _stadt_coords(p_stadt)
                    if not coords or _distanz_km(zentrum, coords) > km_radius:
                        continue
                elif km_radius and not zentrum:
                    if stadt_f and stadt_f not in p_stadt.lower():
                        continue
                elif umkreis == "stadt":
                    if stadt_f and stadt_f not in p_stadt.lower():
                        continue

            online = _ist_online(rec)
            verifiziert = False 
            neu = _ist_neu(rec)
            if status == "online" and not online:
                continue
            if status == "verifiziert" and not verifiziert:
                continue
            if status == "neu" and not neu:
                continue

            sicht = profil.get("sichtbarkeit", {}) or {}
            name_oeff = sicht.get("vorname", "oeffentlich") == "oeffentlich"
            foto_oeff = sicht.get("foto", "oeffentlich") == "oeffentlich"
            standort_oeff = sicht.get("standort", "oeffentlich") != "privat"
            anzeige = voller_name if (name_oeff and voller_name) else (handle or "Mitglied")
            initial = (anzeige[:1] or "#").upper()

            if buchstabe:
                if buchstabe == "#":
                    if initial.isalpha():
                        continue
                elif initial != buchstabe:
                    continue

            treffer.append({
                "ref": handle,
                "handle": handle,
                "name": anzeige,
                "profilbild": profil.get("profilbild", "") if foto_oeff else "",
                "land": p_land if standort_oeff else "",
                "stadt": p_stadt if standort_oeff else "",
                "online": online, "verifiziert": verifiziert, "neu": neu,
                "initial": initial,
                "ich": rec.get("email") == email,
            })
    except Exception as e:
        print(f"Fehler bei /api/profil/suche: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Suche fehlgeschlagen."})

    treffer.sort(key=lambda t: (not t["online"], t["name"].lower()))
    gesamt = len(treffer)
    seite = treffer[offset:offset + limit]
    return {"success": True, "anzahl": gesamt, "treffer": seite,
            "mehr": (offset + limit) < gesamt, "gezielt": gezielt}

@router.get("/api/profil/oeffentlich")
async def profil_oeffentlich(email: str = "", ref: str = ""):
    email = (email or "").lower().strip()
    if not konto_ist_aktiv(email):
        return zugang_verweigert_antwort()
    if not darf_profilsuche(email):
        return rolle_gesperrt_antwort("verifiziert")
    ref = (ref or "").strip()
    if not ref:
        return JSONResponse(status_code=400, content={"success": False, "message": "Kein Profil angegeben."})
    
    database = _get_db()
    if database is None:
        return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

    rec = database.codes.find_one({"profil.benutzername": ref, "konto_status": "aktiv"})
    if not rec:
        return JSONResponse(status_code=404, content={"success": False, "message": "Profil nicht gefunden."})
    profil = rec.get("profil", {}) or {}
    sicht = profil.get("sichtbarkeit", {}) or {}
    def _sichtbar(feld, wert):
        return wert if sicht.get(feld, "oeffentlich") != "privat" else ""
    vorname = profil.get("vorname", "") or ""
    nachname = profil.get("nachname", "") or ""
    standort_ok = sicht.get("standort", "oeffentlich") != "privat"
    
    def canvas_oeffentlich_filtern(canvas, sicht=None):
        if not isinstance(canvas, dict):
            return {}
        sicht = sicht or {}
        def _privat(feld):
            return str(sicht.get(feld, "oeffentlich")).lower() == "privat"
        typ_flag = {"foto": "foto", "bio": "biografie", "name": "vorname", "datum": "geburtsdatum", "standort": "standort"}
        sicher = dict(canvas)
        behalten = []
        for el in (canvas.get("elemente") or []):
            if not isinstance(el, dict):
                continue
            typ = el.get("typ")
            if typ == "galerie" and (str(el.get("sichtbar", "oeffentlich")).lower() == "privat" or _privat("galerie")):
                continue
            flag = typ_flag.get(typ)
            if flag and _privat(flag):
                continue
            behalten.append(el)
        sicher["elemente"] = behalten
        return sicher

    return {
        "success": True,
        "handle": profil.get("benutzername", ""),
        "name": _sichtbar("vorname", f"{vorname} {nachname}".strip()) or (profil.get("benutzername", "") or "Mitglied"),
        "profilbild": _sichtbar("foto", profil.get("profilbild", "")),
        "biografie": _sichtbar("biografie", profil.get("biografie", "")),
        "geburtsdatum": _sichtbar("geburtsdatum", profil.get("geburtsdatum", "")),
        "land": profil.get("land", "") if standort_ok else "",
        "stadt": profil.get("stadt", "") if standort_ok else "",
        "galerie": profil.get("galerie", []) if sicht.get("galerie", "oeffentlich") != "privat" else [],
        "galerie_seite": profil.get("galerie_seite", {}) if sicht.get("galerie", "oeffentlich") != "privat" else {},
        "canvas": canvas_oeffentlich_filtern(profil.get("canvas", {}) or {}, sicht),
    }

@router.get("/api/sektoren/status")
async def sektoren_status(email: str = ""):
    email = (email or "").lower().strip()
    if not konto_ist_aktiv(email):
        return zugang_verweigert_antwort()
    try:
        _prune_video_raum()
    except Exception:
        pass
        
    database = _get_db()
    sektoren = []
    for s in range(1, ANZAHL_THEMEN_GESAMT + 1):
        beitraege = 0
        live = 0
        if database is not None:
            try:
                beitraege = database.forum_beitraege.count_documents({"sektor": s})
            except Exception:
                pass
            try:
                live = database.video_raum.count_documents({"raum": str(s)})
            except Exception:
                pass
        sektoren.append({
            "sektor": s,
            "thema": SEKTOR_THEMEN.get(str(s), f"Sektor {s}"),
            "gesperrt": thema_fuer_user_gesperrt(s, email),
            "beitraege": beitraege,
            "live_teilnehmer": live,
        })
    return {"success": True, "sektoren": sektoren}

@router.get("/api/rolle")
async def api_rolle(email: str = ""):
    email = (email or "").lower().strip()
    if not konto_ist_aktiv(email):
        return zugang_verweigert_antwort()
    rolle = bestimme_rolle(email)
    limit = ROLLE_POST_LIMIT().get(rolle, 1)
    heute = posts_heute(email)
    return {
        "success": True,
        "rolle": rolle,
        "post_limit": limit,
        "posts_heute": heute,
        "verbleibende_posts": max(0, limit - heute),
        "darf_profilsuche": darf_profilsuche(email),
        "darf_live": ist_premium(email),
        "darf_reservieren": ist_premium(email),
        "darf_einladen": ist_premium(email),
    }

@router.post("/api/support")
async def api_support(request: Request):
    try:
        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()

        try:
            sektor = str(int(data.get("sektor", 1)))
        except (TypeError, ValueError):
            sektor = "1"
        nachricht = (data.get("message") or "").strip()
        if not nachricht:
            return {"success": False, "message": "Leere Anfrage."}

        if not ki_aktiv_fuer_sektor(sektor):
            return {
                "success": True, "ki_aktiv": False, "sektor": sektor, "seele": "M&M Support",
                "reply": "Der KI-Support ist für dieses Thema derzeit deaktiviert. Bitte tausche dich direkt im Stream mit der Community aus.",
            }

        seele, seele_wesen = hole_seele(sektor)
        thema = SEKTOR_THEMEN.get(sektor, "die M&M Community")
        sektor_gesetz = hole_sektor_gesetz(sektor)

        gesetz_block = (
            f"\n\nVERBINDLICHE THEMENDEFINITION / SICHTWEISE DIESES SEKTORS "
            f"(vom Architekten der M&M Community festgelegt – RICHTE DEIN VERHALTEN, DEINE "
            f"ANSPRACHE UND DEINE SUPPORT-LOGIK STRIKT DANACH AUS):\n\"\"\"{sektor_gesetz}\"\"\"\n"
            if sektor_gesetz else ""
        )
        system = (
            f"Du bist der M&M Community Support. Du wirst DYNAMISCH als die Seele '{seele}' "
            f"des Sektors {sektor} geladen (Thema: '{thema}').\n"
            f"Deine Wesensart: {seele_wesen}"
            f"{gesetz_block}\n\n"
            "AUFTRAG: Hilf dem Menschen freundlich, klar und konkret bei Fragen zur Plattform, "
            "zur Bedienung des 3-Spalten-Dashboards (Themen-Stream, Live-Sektor) und zu diesem Thema. "
            "Wenn eine Themendefinition/Sichtweise oben vorgegeben ist, ist sie für dich Gesetz: "
            "vertritt sie konsequent (z. B. der Grundsatz, dass Mensch gleich Mensch ist) und weiche nicht davon ab. "
            "Antworte kurz (maximal 4 Sätze), respektvoll und im Geist des Rechts auf Gefühlsvorderung. "
            "Bleibe in der Rolle deiner Sektor-Seele, ohne esoterisch zu übertreiben."
        )

        api_key = os.getenv("GEMINI_API_KEY", "").strip().replace("[", "").replace("]", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        contents = [
            {"role": "user", "parts": [{"text": f"SYSTEM-ANWEISUNG:\n{system}"}]},
            {"role": "model", "parts": [{"text": f"Verstanden. Ich bin als {seele} für dich da."}]},
            {"role": "user", "parts": [{"text": nachricht}]},
        ]
        resp = requests.post(url, json={"contents": contents}, timeout=30)
        res_data = resp.json()
        if resp.status_code == 200 and "candidates" in res_data:
            reply = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            reply = f"{seele}: Ich bin gleich wieder für dich da – der Support-Dienst antwortet gerade nicht."

        return {"success": True, "reply": reply, "seele": seele, "sektor": sektor, "thema": thema}
    except Exception as e:
        print(f"Fehler bei /api/support: {e}")
        return {"success": False, "message": "Systemfehler im Support."}

@router.get("/api/abo/status")
async def abo_status(email: str = ""):
    email = (email or "").lower().strip()
    return {"success": True, "abo_aktiv": hat_aktives_abo(email)}

@router.post("/api/abo/aktivieren")
async def abo_aktivieren(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        database.codes.update_one(
            {"email": email},
            {"$set": {"abo_aktiv": True, "abo_seit": datetime.now()}},
        )
        return {"success": True, "abo_aktiv": True, "message": "Abo aktiviert – Sektor 22 (Video-Beweis) freigeschaltet."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})