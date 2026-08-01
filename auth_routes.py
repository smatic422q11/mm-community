from __future__ import annotations

import os
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth

from models import RegisterModell
from models import wandle_mongo_daten_um
from mail_services import send_verification_email

letzte_anfragen = {}

class AuthRouterConfig:
    """Saubere DI-Konfiguration für den Auth-Router."""
    def __init__(self) -> None:
        self.database = None
        self.ws_manager = None
        self.module_service = None
        self.utils_module = None
        self.mail_service = None

_auth_config = AuthRouterConfig()

def set_auth_router_config(
    database: Any = None,
    ws_manager: Any = None,
    module_service_instance: Any = None,
    utils_module: Any = None,
    mail_service: Any = None,
) -> None:
    """Konfiguration injizieren, ohne Router untereinander zu koppeln."""
    _auth_config.database = database
    _auth_config.ws_manager = ws_manager
    _auth_config.module_service = module_service_instance
    _auth_config.utils_module = utils_module
    _auth_config.mail_service = mail_service

def _get_db():
    if _auth_config.database is not None:
        return _auth_config.database
    try:
        from database import database_service
        return database_service.get_db()
    except Exception:
        return None
    
router = APIRouter()

# --- OAUTH SETUP FÜR GOOGLE ---
load_dotenv()
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

ADMIN_EMAILS = {"mmcommunity22@gmail.com"}

# --- Globale Admin Einstellungen (Korrigiert auf 20 Themen) ---
SEKTOR_THEMEN = {
    "1": "Recht auf Gefühlsvorderung", "2": "Wie werde ich Mensch", "3": "Glaube an Friede",
    "4": "Programm für Bürgerliche Rechte", "5": "Moralische Pflicht und Verantwortung",
    "6": "Menschlichkeit Wiederherstellung", "7": "Kinderschutz-Pflicht-Elternrechte",
    "8": "Wahre Richtung und Kunst", "9": "LGBTQ und Kirche", "10": "Trend und Tradition",
    "11": "Religionsbekenntnis oder Selbstwahl", "12": "Gesundheitswesen und Verhalten",
    "13": "Arbeitswelt und Du", "14": "Mobbing am Arbeitsplatz", "15": "Jugendsprecher",
    "16": "Ratgeber für Pensionisten", "17": "Sozialgefallen und Widerkehr",
    "18": "Nachbarschaft und Gemeinschaft", "19": "Alleinerziehend", "20": "Die Brücke"
}

SECTOR_NAMES = {"1": "Seele 1"} # Fallbacks
GESPERRTE_THEMEN_FUER_USER = set()
ANZAHL_THEMEN_GESAMT = 20
LIVE_SLOTS = {"vormittag", "nachmittag"}
LIVE_DEFAULT_DAUER_MIN = 60
VIDEO_DEFAULT_PLAETZE_PRO_TISCH = 8

def ist_admin(email: str) -> bool:
    return (email or "").lower().strip() in ADMIN_EMAILS

def _hash_passwort(passwort: str, salt: str = None):
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", (passwort or "").encode("utf-8"), salt.encode("utf-8"), 120000)
    return salt, dk.hex()

def pruefe_passwort(passwort: str, salt: str, erwartet_hash: str) -> bool:
    if not salt or not erwartet_hash:
        return False
    _, kandidat = _hash_passwort(passwort, salt)
    return secrets.compare_digest(kandidat, erwartet_hash)

def generiere_bestaetigungscode() -> str:
    return str(secrets.randbelow(900000) + 100000)

def konto_ist_aktiv(email: str) -> bool:
    email = (email or "").lower().strip()
    if ist_admin(email):
        return True
    
    database = _get_db()
    if database is None:
        return False
        
    rec = database.codes.find_one({"email": email})
    if not rec:
        return False
    if rec.get("konto_status") == "aktiv":
        return True
    return bool((rec.get("profil") or {}).get("vollstaendig"))

def zugang_verweigert_antwort():
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "zugang": "gesperrt",
            "message": "Zugriff verweigert. Bitte zuerst registrieren, E-Mail bestätigen und das Profil vollständig ausfüllen.",
        },
    )

def hat_wahrheits_zertifikat(email: str) -> bool:
    email = (email or "").lower().strip()
    if ist_admin(email):
        return True
    database = _get_db()
    if database is None:
        return False
    rec = database.codes.find_one({"email": email}, {"abgeschlossene_sektoren": 1})
    if not rec:
        return False
    abgeschlossene = {str(s) for s in (rec.get("abgeschlossene_sektoren", []) or [])}
    return "1" in abgeschlossene

def hat_aktives_abo(email: str) -> bool:
    email = (email or "").lower().strip()
    if ist_admin(email):
        return True
    database = _get_db()
    if database is None:
        return False
    rec = database.codes.find_one({"email": email}, {"abo_aktiv": 1})
    return bool(rec and rec.get("abo_aktiv"))

def profil_ist_verifiziert(rec: dict) -> bool:
    profil = (rec or {}).get("profil", {}) or {}
    return (
        bool(profil.get("vollstaendig"))
        and bool(profil.get("profilbild"))
        and bool((profil.get("vorname") or "").strip())
        and bool((profil.get("nachname") or "").strip())
    )

def bestimme_rolle(email: str) -> str:
    email = (email or "").lower().strip()
    if ist_admin(email):
        return "admin"
    database = _get_db()
    if database is None:
        return "gast"
    rec = database.codes.find_one({"email": email})
    if not rec:
        return "gast"
    if rec.get("abo_aktiv"):
        return "premium"
    if profil_ist_verifiziert(rec) or rec.get("admin_verifiziert"):
        return "verifiziert"
    return "basis"

def _auth_erfolgs_payload(record: dict) -> dict:
    email = record.get("email", "")
    admin = ist_admin(email)
    rolle = "admin" if admin else record.get("role", "user")
    profil = record.get("profil", {}) or {}
    return {
        "success": True,
        "role": rolle,
        "co_assistent_modus": admin,
        "history": record.get("history", []),
        "abo_aktiv": hat_aktives_abo(email),
        "profil": {
            "vorname": profil.get("vorname", ""),
            "nachname": profil.get("nachname", ""),
            "benutzername": profil.get("benutzername", ""),
            "biografie": profil.get("biografie", ""),
            "profilbild": profil.get("profilbild", ""),
            "hat_bild": bool(profil.get("profilbild")),
        },
    }

# --- CANVAS & GALERIE NORMALISIERUNG ---
CANVAS_ELEMENT_TYPEN = {"bio", "motto", "text", "foto", "galerie", "name", "datum", "standort"}
CANVAS_AUSRICHTUNG = {"links", "zentriert", "rechts"}
CANVAS_MASKE = {"", "kreis"}
CANVAS_PASSUNG = {"cover", "contain"}
MAX_CANVAS_ELEMENTE = 60
MAX_GALERIE_BILDER = 24
MAX_BILD_BYTES = 2_500_000

def _canvas_zahl(wert, standard, lo, hi):
    try:
        n = float(wert)
    except (TypeError, ValueError):
        return standard
    if n != n:
        return standard
    return max(lo, min(hi, n))

def _canvas_bild(wert):
    if isinstance(wert, str) and wert and len(wert) <= MAX_BILD_BYTES:
        return wert
    return ""

def normalisiere_canvas_element(el):
    if not isinstance(el, dict):
        return None
    typ = str(el.get("typ", "text"))[:20]
    if typ not in CANVAS_ELEMENT_TYPEN:
        typ = "text"
    ausrichtung = str(el.get("ausrichtung", "links"))[:12]
    if ausrichtung not in CANVAS_AUSRICHTUNG:
        ausrichtung = "links"
    maske = str(el.get("maske", ""))[:12]
    if maske not in CANVAS_MASKE:
        maske = ""
    bild_passung = str(el.get("bild_passung", "cover"))[:10]
    if bild_passung not in CANVAS_PASSUNG:
        bild_passung = "cover"
    norm = {
        "typ": typ,
        "x": _canvas_zahl(el.get("x"), 5, 0, 100),
        "y": _canvas_zahl(el.get("y"), 5, 0, 100),
        "w": _canvas_zahl(el.get("w"), 30, 3, 100),
        "h": _canvas_zahl(el.get("h"), 18, 3, 100),
        "z": int(_canvas_zahl(el.get("z"), 0, 0, 999)),
        "maske": maske,
        "freistellen": bool(el.get("freistellen")),
        "bild_passung": bild_passung,
        "text": str(el.get("text", ""))[:6000],
        "label": str(el.get("label", ""))[:120],
        "farbe": str(el.get("farbe", ""))[:32],
        "groesse": _canvas_zahl(el.get("groesse"), 1, 0.4, 8),
        "zeilenabstand": _canvas_zahl(el.get("zeilenabstand"), 1.35, 0.8, 3.5),
        "ausrichtung": ausrichtung,
        "fett": bool(el.get("fett")),
        "radius": _canvas_zahl(el.get("radius"), 10, 0, 300),
        "bg_farbe": str(el.get("bg_farbe", ""))[:32],
        "rahmen_farbe": str(el.get("rahmen_farbe", ""))[:32],
        "rahmen_breite": _canvas_zahl(el.get("rahmen_breite"), 0, 0, 40),
        "polster": _canvas_zahl(el.get("polster"), 0, 0, 100),
        "bild": _canvas_bild(el.get("bild")),
        "filter": str(el.get("filter", ""))[:60],
    }
    if typ == "galerie":
        bilder = []
        for b in (el.get("bilder") or [])[:MAX_GALERIE_BILDER]:
            gute = _canvas_bild(b)
            if gute:
                bilder.append(gute)
        norm["bilder"] = bilder
        norm["spalten"] = int(_canvas_zahl(el.get("spalten"), 3, 1, 8))
        norm["luecke"] = _canvas_zahl(el.get("luecke"), 8, 0, 40)
        norm["sichtbar"] = "privat" if str(el.get("sichtbar", "oeffentlich")).lower() == "privat" else "oeffentlich"
    return norm

def normalisiere_canvas(c):
    if not isinstance(c, dict):
        c = {}
    elemente = []
    for el in (c.get("elemente") or [])[:MAX_CANVAS_ELEMENTE]:
        norm = normalisiere_canvas_element(el)
        if norm:
            elemente.append(norm)
    return {
        "hintergrund_url": str(c.get("hintergrund_url", ""))[:600],
        "hintergrund_farbe": str(c.get("hintergrund_farbe", ""))[:32],
        "hintergrund_pos_x": _canvas_zahl(c.get("hintergrund_pos_x"), 50, 0, 100),
        "hintergrund_pos_y": _canvas_zahl(c.get("hintergrund_pos_y"), 50, 0, 100),
        "hintergrund_skala": _canvas_zahl(c.get("hintergrund_skala"), 100, 30, 300),
        "farbschema": str(c.get("farbschema", ""))[:40],
        "rahmen": str(c.get("rahmen", ""))[:60],
        "elemente": elemente,
    }

GALERIE_FILTER_WHITELIST = {"", "none", "grayscale(1)", "sepia(0.7)", "contrast(1.3)", "saturate(1.7)", "brightness(1.2)", "blur(1.5px)"}
MAX_GALERIE_SEITE_BILDER = 60

def _galerie_seite_bild(b):
    if isinstance(b, str):
        b = {"url": b}
    if not isinstance(b, dict):
        return None
    url = _canvas_bild(b.get("url"))
    if not url:
        return None
    filt = str(b.get("filter", ""))[:60]
    if filt not in GALERIE_FILTER_WHITELIST:
        filt = ""
    return {"url": url, "titel": str(b.get("titel", ""))[:160], "filter": filt}

def normalisiere_galerie_seite(g):
    if not isinstance(g, dict):
        return {}
    bilder = []
    for b in (g.get("bilder") or [])[:MAX_GALERIE_SEITE_BILDER]:
        nb = _galerie_seite_bild(b)
        if nb:
            bilder.append(nb)
    elemente = []
    for el in (g.get("elemente") or [])[:MAX_CANVAS_ELEMENTE]:
        norm = normalisiere_canvas_element(el)
        if norm:
            elemente.append(norm)
    return {
        "hintergrund_url": str(g.get("hintergrund_url", ""))[:600],
        "hintergrund_farbe": str(g.get("hintergrund_farbe", ""))[:32],
        "hintergrund_pos_x": _canvas_zahl(g.get("hintergrund_pos_x"), 50, 0, 100),
        "hintergrund_pos_y": _canvas_zahl(g.get("hintergrund_pos_y"), 50, 0, 100),
        "hintergrund_skala": _canvas_zahl(g.get("hintergrund_skala"), 100, 30, 300),
        "farbschema": str(g.get("farbschema", ""))[:40],
        "rahmen": str(g.get("rahmen", ""))[:60],
        "bilder": bilder,
        "elemente": elemente,
    }

@router.post("/auth/register")
async def auth_register(daten: RegisterModell, request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        # --- 1. WAHRE IP ABFANGEN (Trotz Cloudflare/Render) ---
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host

        # --- 2. EISERNES IP-SCHILD IN DER DATENBANK ---
        jetzt = datetime.now(timezone.utc)
        ip_sperre = database.ip_sperren.find_one({"ip": client_ip})
        if ip_sperre:
            letzte_zeit = ip_sperre.get("zeit")
            if letzte_zeit:
                # NEU: Zeitzonen-Reparatur! Macht alte, "naive" Zeiten fit fürs Rechnen.
                if letzte_zeit.tzinfo is None:
                    letzte_zeit = letzte_zeit.replace(tzinfo=timezone.utc)
                
                if (jetzt - letzte_zeit) < timedelta(hours=1):
                    return JSONResponse(
                        status_code=429, 
                        content={"success": False, "message": "Spam-Schutz: Zu viele Anfragen. Bitte warte eine Stunde."}
                    )

        database.ip_sperren.update_one(
            {"ip": client_ip},
            {"$set": {"zeit": jetzt}},
            upsert=True
        )

        email = daten.email.lower().strip()
        real_name = daten.real_name.strip()
        passwort = daten.passwort

        # ==========================================
        # --- NEU: EISERNE BACKEND-VALIDIERUNG ---
        # ==========================================

        # A) E-Mail Format per Regex im Backend prüfen
        import re
        email_regex = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(email_regex, email):
            return JSONResponse(status_code=400, content={"success": False, "message": "Bitte gib eine formell gültige E-Mail-Adresse ein."})

        # B) Echter Name (Mindestens Vor- und Nachname)
        if len(real_name.split()) < 2:
            return JSONResponse(status_code=400, content={"success": False, "message": "Bitte gib deinen echten Vor- und Nachnamen an (Vor- und Nachname)."})

        # C) Passwort-Länge absichern (Mindestens 6 Zeichen)
        if not passwort or len(passwort) < 6:
            return JSONResponse(status_code=400, content={"success": False, "message": "Das Passwort muss mindestens 6 Zeichen lang sein."})

        # D) NEU: AGB-Prüfung im Backend
        if not daten.agb_akzeptiert:
            return JSONResponse(status_code=400, content={"success": False, "message": "Die Nutzungsbedingungen müssen akzeptiert werden."})

        # ==========================================

        bestehend = database.codes.find_one({"email": email})
        if bestehend and bestehend.get("konto_status") == "aktiv":
            return {"success": False, "status": "existiert", "message": "Dieses Konto ist bereits registriert. Bitte einloggen."}

        salt, pass_hash = _hash_passwort(passwort)
        code = generiere_bestaetigungscode()

        basis = {
            "email": email,
            "code": code,
            "real_name": real_name,
            "pass_salt": salt,
            "pass_hash": pass_hash,
            "agb_akzeptiert_am": datetime.now(timezone.utc),
            "konto_status": "pending",
            "email_verifiziert": False,
            "role": "admin" if ist_admin(email) else "user",
            "letztes_update": datetime.now(timezone.utc), # Hier sichern wir ab sofort auch die Zeitzone!
        }
        
        if bestehend:
            database.codes.update_one({"email": email}, {"$set": basis})
        else:
            basis.update({
                "manifest_mode": None,
                "drawer_opened": False,
                "created_at": datetime.now(timezone.utc), # Und hier auch!
                "history": [],
                "fortschritt": 0,
                "profil": {"vollstaendig": False},
            })
            database.codes.insert_one(basis)

        success = send_verification_email(email, code)
        return {
            "success": True,
            "status": "registriert",
            "email_gesendet": success,
            "message": (
                "Registrierung erfasst. Wir haben dir einen 6-stelligen Bestätigungscode per E-Mail gesendet." if success else
                "Registrierung erfasst, aber der Code konnte nicht versendet werden. Bitte später erneut anfordern."
            ),
        }
    except Exception as e:
        print(f"Fehler bei /auth/register: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler bei der Registrierung."})
    
@router.post("/auth/verify-code")
async def auth_verify_code(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = data.get("email", "").lower().strip()
        code = str(data.get("code", "")).strip()

        record = database.codes.find_one({"email": email})
        if not record:
            return JSONResponse(status_code=404, content={"success": False, "message": "Kein Konto gefunden. Bitte zuerst registrieren."})
        if str(record.get("code")) != code:
            return JSONResponse(status_code=401, content={"success": False, "message": "Der Bestätigungscode ist ungültig."})

        profil_vollstaendig = bool((record.get("profil") or {}).get("vollstaendig"))
        neuer_status = "aktiv" if profil_vollstaendig else "verified"
        database.codes.update_one(
            {"email": email},
            {"$set": {"email_verifiziert": True, "konto_status": neuer_status, "letztes_update": datetime.now()}},
        )
        return {
            "success": True,
            "email_verifiziert": True,
            "needs_profil": not profil_vollstaendig,
            "message": "E-Mail erfolgreich bestätigt.",
        }
    except Exception as e:
        print(f"Fehler bei /auth/verify-code: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler bei der Validierung."})

@router.post("/auth/resend-code")
async def auth_resend_code(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = data.get("email", "").lower().strip()
        record = database.codes.find_one({"email": email})
        if not record or not record.get("code"):
            return JSONResponse(status_code=404, content={"success": False, "message": "Kein Konto gefunden."})
        success = send_verification_email(email, str(record.get("code")))
        return {"success": True, "email_gesendet": success, "message": "Der Bestätigungscode wurde erneut gesendet."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@router.post("/auth/login")
async def auth_login(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = data.get("email", "").lower().strip()
        passwort = data.get("passwort") or data.get("password") or ""

        record = database.codes.find_one({"email": email})
        if not record or not record.get("pass_hash"):
            return JSONResponse(status_code=401, content={"success": False, "message": "Konto nicht gefunden oder noch nicht registriert (eventuell Google Login?)."})
        if not pruefe_passwort(passwort, record.get("pass_salt"), record.get("pass_hash")):
            return JSONResponse(status_code=401, content={"success": False, "message": "E-Mail oder Passwort ist falsch."})

        if not record.get("email_verifiziert"):
            return {"success": True, "stufe": "verify", "message": "Bitte bestätige zuerst deine E-Mail."}
        if not (record.get("profil") or {}).get("vollstaendig"):
            return {"success": True, "stufe": "profil", "message": "Bitte vervollständige zuerst dein Profil."}

        payload = _auth_erfolgs_payload(record)
        payload["stufe"] = "dashboard"
        return payload
    except Exception as e:
        print(f"Fehler bei /auth/login: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler beim Login."})

@router.post("/auth/profil")
async def auth_profil(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = data.get("email", "").lower().strip()
        vorname = (data.get("vorname") or "").strip()
        nachname = (data.get("nachname") or "").strip()
        benutzername = (data.get("benutzername") or data.get("handle") or "").strip()
        profilbild = data.get("profilbild") or ""

        record = database.codes.find_one({"email": email})
        if not record:
            return JSONResponse(status_code=404, content={"success": False, "message": "Kein Konto gefunden."})
        if not record.get("email_verifiziert"):
            return JSONResponse(status_code=403, content={"success": False, "message": "Bitte zuerst die E-Mail bestätigen."})

        if not vorname or not nachname:
            return JSONResponse(status_code=400, content={"success": False, "message": "Echter Vor- und Nachname sind Pflicht."})
        if not benutzername:
            return JSONResponse(status_code=400, content={"success": False, "message": "Bitte einen Benutzernamen/Handle wählen."})

        if profilbild and len(profilbild) > 2_500_000:
            profilbild = ""

        profil = {
            "vorname": vorname,
            "nachname": nachname,
            "benutzername": benutzername,
            "profilbild": profilbild,
            "vollstaendig": True,
            "gespeichert_am": datetime.now(),
        }
        database.codes.update_one(
            {"email": email},
            {"$set": {
                "profil": profil,
                "name": f"{vorname} {nachname}",
                "konto_status": "aktiv",
                "letztes_update": datetime.now(),
            }},
        )
        record = database.codes.find_one({"email": email})
        payload = _auth_erfolgs_payload(record)
        payload["stufe"] = "dashboard"
        payload["message"] = "Profil gespeichert. Voller Zugang freigeschaltet."
        return payload
    except Exception as e:
        print(f"Fehler bei /auth/profil: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler beim Speichern des Profils."})

@router.get("/auth/status")
async def auth_status(email: str):
    database = _get_db()
    if database is None:
        return {"registriert": False, "email_verifiziert": False, "profil_vollstaendig": False, "zugang_frei": False}
    email = (email or "").lower().strip()
    record = database.codes.find_one({"email": email})
    if not record:
        return {"registriert": False, "email_verifiziert": False, "profil_vollstaendig": False, "zugang_frei": False}
    profil_vollstaendig = bool((record.get("profil") or {}).get("vollstaendig"))
    return {
        "registriert": True,
        "email_verifiziert": bool(record.get("email_verifiziert")),
        "profil_vollstaendig": profil_vollstaendig,
        "zugang_frei": konto_ist_aktiv(email),
        "konto_status": record.get("konto_status", "pending"),
        "hat_zertifikat": hat_wahrheits_zertifikat(email),
        "abo_aktiv": hat_aktives_abo(email),
    }

@router.get("/auth/profil-daten")
async def auth_profil_daten(email: str):
    try:
        email = (email or "").lower().strip()
        
        try:
            if not konto_ist_aktiv(email):
                return zugang_verweigert_antwort()
        except Exception:
            pass 
            
        database = _get_db()
        
        rec = (database.codes.find_one({"email": email}) if database is not None else None) or {}
        profil = rec.get("profil", {}) or {}
        
        return {
            "success": True,
            "email": email,
            "vorname": profil.get("vorname", ""),
            "nachname": profil.get("nachname", ""),
            "benutzername": profil.get("benutzername", ""),
            "biografie": profil.get("biografie", ""),
            "profilbild": profil.get("profilbild", ""),
            "geburtsdatum": profil.get("geburtsdatum", ""),
            "galerie": profil.get("galerie", []),
            "galerie_seite": profil.get("galerie_seite", {}),
            "sichtbarkeit": profil.get("sichtbarkeit", {}),
            "layout": profil.get("layout", []),
            "farbschema": profil.get("farbschema", ""),
            "canvas": profil.get("canvas", {}),
            "land": profil.get("land", ""),
            "stadt": profil.get("stadt", ""),
            "konto_status": rec.get("konto_status", "aktiv"),
            "abo_aktiv": bool(rec.get("abo_aktiv")),
            "rolle": bestimme_rolle(email),
            "ist_admin": ist_admin(email),
        }
    except Exception as e:
        print(f"🔥 FEHLER BEI /auth/profil-daten: {e}")
        return {"success": False, "error": str(e)}

@router.post("/auth/profil-update")
async def auth_profil_update(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        rec = database.codes.find_one({"email": email})
        if not rec:
            return JSONResponse(status_code=404, content={"success": False, "message": "Kein Konto gefunden."})

        profil = rec.get("profil", {}) or {}
        set_data = {"letztes_update": datetime.now()}

        vorname = (data.get("vorname") or "").strip()
        nachname = (data.get("nachname") or "").strip()
        benutzername = (data.get("benutzername") or data.get("handle") or "").strip()
        if vorname:
            profil["vorname"] = vorname
        if nachname:
            profil["nachname"] = nachname
        if benutzername:
            profil["benutzername"] = benutzername
        if vorname or nachname:
            set_data["name"] = f"{profil.get('vorname','')} {profil.get('nachname','')}".strip()

        if "biografie" in data:
            profil["biografie"] = (data.get("biografie") or "").strip()[:2000]

        if "profilbild" in data:
            neues_bild = data.get("profilbild") or ""
            if neues_bild and len(neues_bild) > 2_500_000:
                return JSONResponse(status_code=400, content={"success": False, "message": "Das Bild ist zu groß (max ~2,5 MB)."})
            profil["profilbild"] = neues_bild

        if "geburtsdatum" in data:
            profil["geburtsdatum"] = (data.get("geburtsdatum") or "").strip()[:10]

        if "sichtbarkeit" in data and isinstance(data.get("sichtbarkeit"), dict):
            erlaubte_felder = {"vorname", "nachname", "geburtsdatum", "biografie", "foto", "galerie", "standort"}
            sicht = {}
            for feld, wert in data["sichtbarkeit"].items():
                if feld in erlaubte_felder:
                    sicht[feld] = "privat" if str(wert).lower() == "privat" else "oeffentlich"
            profil["sichtbarkeit"] = sicht

        if "layout" in data and isinstance(data.get("layout"), list):
            erlaubte_kacheln = {"foto", "vorname", "nachname", "geburtsdatum", "biografie", "galerie"}
            profil["layout"] = [k for k in data["layout"] if k in erlaubte_kacheln]

        if "farbschema" in data:
            profil["farbschema"] = (data.get("farbschema") or "").strip()[:40]

        if "galerie" in data and isinstance(data.get("galerie"), list):
            galerie = []
            for bild in data["galerie"][:8]:
                if isinstance(bild, str) and bild and len(bild) <= 2_000_000:
                    galerie.append(bild)
            profil["galerie"] = galerie

        if "galerie_seite" in data and isinstance(data.get("galerie_seite"), dict):
            profil["galerie_seite"] = normalisiere_galerie_seite(data.get("galerie_seite"))

        if "land" in data:
            profil["land"] = (data.get("land") or "").strip()[:80]
        if "stadt" in data:
            profil["stadt"] = (data.get("stadt") or "").strip()[:80]

        if "canvas" in data and isinstance(data.get("canvas"), dict):
            c = data.get("canvas")
            profil["canvas"] = normalisiere_canvas(c)

        set_data["profil"] = profil
        database.codes.update_one({"email": email}, {"$set": set_data})
        return {
            "success": True,
            "message": "Profil aktualisiert.",
            "profilbild": profil.get("profilbild", ""),
            "biografie": profil.get("biografie", ""),
            "benutzername": profil.get("benutzername", ""),
            "geburtsdatum": profil.get("geburtsdatum", ""),
            "galerie": profil.get("galerie", []),
            "galerie_seite": profil.get("galerie_seite", {}),
            "sichtbarkeit": profil.get("sichtbarkeit", {}),
            "layout": profil.get("layout", []),
            "farbschema": profil.get("farbschema", ""),
        }
    except Exception as e:
        print(f"Fehler bei /auth/profil-update: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler beim Profil-Update."})

@router.post("/auth/passwort-aendern")
async def auth_passwort_aendern(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        altes = data.get("altes_passwort") or data.get("old_password") or ""
        neues = data.get("neues_passwort") or data.get("new_password") or ""

        rec = database.codes.find_one({"email": email})
        if not rec or not rec.get("pass_hash"):
            return JSONResponse(status_code=404, content={"success": False, "message": "Kein Konto gefunden (oder über Google registriert)."})
        if not pruefe_passwort(altes, rec.get("pass_salt"), rec.get("pass_hash")):
            return JSONResponse(status_code=401, content={"success": False, "message": "Das aktuelle Passwort ist falsch."})
        if len(neues) < 6:
            return JSONResponse(status_code=400, content={"success": False, "message": "Das neue Passwort muss mindestens 6 Zeichen haben."})

        salt, pass_hash = _hash_passwort(neues)
        database.codes.update_one(
            {"email": email},
            {"$set": {"pass_salt": salt, "pass_hash": pass_hash, "letztes_update": datetime.now()}},
        )
        return {"success": True, "message": "Passwort erfolgreich geändert."}
    except Exception as e:
        print(f"Fehler bei /auth/passwort-aendern: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler beim Passwort-Wechsel."})

@router.post("/auth/email-aendern")
async def auth_email_aendern(request: Request):
    try:
        database = _get_db()
        if database is None:
            return JSONResponse(status_code=500, content={"success": False, "message": "DB nicht konfiguriert."})

        data = await request.json()
        email = (data.get("email") or "").lower().strip()
        if not konto_ist_aktiv(email):
            return zugang_verweigert_antwort()
        neue_email = (data.get("neue_email") or data.get("new_email") or "").lower().strip()
        passwort = data.get("passwort") or data.get("password") or ""

        if not neue_email or "@" not in neue_email:
            return JSONResponse(status_code=400, content={"success": False, "message": "Bitte eine gültige neue E-Mail angeben."})
        if neue_email == email:
            return JSONResponse(status_code=400, content={"success": False, "message": "Das ist bereits deine aktuelle E-Mail."})

        rec = database.codes.find_one({"email": email})
        if not rec or not rec.get("pass_hash"):
            return JSONResponse(status_code=404, content={"success": False, "message": "Kein Konto gefunden (oder über Google registriert)."})
        if not pruefe_passwort(passwort, rec.get("pass_salt"), rec.get("pass_hash")):
            return JSONResponse(status_code=401, content={"success": False, "message": "Das Passwort ist falsch."})
        if database.codes.find_one({"email": neue_email}):
            return JSONResponse(status_code=409, content={"success": False, "message": "Diese E-Mail wird bereits verwendet."})

        database.codes.update_one({"email": email}, {"$set": {"email": neue_email, "letztes_update": datetime.now()}})
        for coll, feld in ((database.user_progress, "email"), (database.forum_beitraege, "autor_email")):
            try:
                coll.update_many({feld: email}, {"$set": {feld: neue_email}})
            except Exception:
                pass
        return {"success": True, "message": "E-Mail erfolgreich geändert.", "neue_email": neue_email}
    except Exception as e:
        print(f"Fehler bei /auth/email-aendern: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Systemfehler bei der E-Mail-Änderung."})


# =========================================================
# === NEUE GOOGLE OAUTH ROUTEN (Hier fängt die Magie an) ===
# =========================================================

@router.get("/auth/google")
async def login_via_google(request: Request):
    """Leitet den User zur Google-Anmeldeseite weiter"""
    # Wir zwingen Google exakt auf diese Adresse, damit es keine Verwirrung mehr gibt!
    redirect_uri = "http://localhost:10000/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    """Verarbeitet die Google-Antwort und loggt den User in der M&M Community ein"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        
        if not user_info:
            return RedirectResponse(url="/?error=auth_failed")

        email = user_info.get("email", "").lower().strip()
        name = user_info.get("name", "")
        picture = user_info.get("picture", "")
        given_name = user_info.get("given_name", "")
        family_name = user_info.get("family_name", "")
        
        database = _get_db()
        if database is not None:
            record = database.codes.find_one({"email": email})
            if not record:
                # User ist komplett neu -> Wir legen ihn direkt als E-Mail-verifiziert an
                basis = {
                    "email": email,
                    "real_name": name,
                    "pass_salt": "", # Google-Logins brauchen kein Passwort bei uns
                    "pass_hash": "",
                    "konto_status": "aktiv", # Status aktiv, auch wenn Profil noch unvollständig
                    "email_verifiziert": True,
                    "role": "admin" if ist_admin(email) else "user",
                    "letztes_update": datetime.now(),
                    "manifest_mode": None,
                    "drawer_opened": False,
                    "created_at": datetime.now(),
                    "history": [],
                    "fortschritt": 0,
                    "profil": {
                        "vollstaendig": False, # Das Profil muss er im Frontend noch fertig ausfüllen
                        "vorname": given_name,
                        "nachname": family_name,
                        "profilbild": picture
                    },
                }
                database.codes.insert_one(basis)
            else:
                # User existiert schon -> Wir setzen seine E-Mail auf verifiziert, falls sie es nicht war
                if not record.get("email_verifiziert"):
                    profil_vollstaendig = bool((record.get("profil") or {}).get("vollstaendig"))
                    neuer_status = "aktiv" if profil_vollstaendig else "verified"
                    database.codes.update_one(
                        {"email": email}, 
                        {"$set": {"email_verifiziert": True, "konto_status": neuer_status, "letztes_update": datetime.now()}}
                    )

        # Nach erfolgreichem Login leiten wir ans Frontend weiter.
        # Über den URL-Parameter weiß dein Frontend, dass der Login geklappt hat!
        return RedirectResponse(url=f"/?google_login=success&email={email}")

    except Exception as e:
        print(f"Fehler bei Google Callback: {e}")
        return RedirectResponse(url="/?error=google_login_failed")
