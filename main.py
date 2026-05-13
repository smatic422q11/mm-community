import os
import certifi
import requests
import random
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from fastapi.responses import JSONResponse 

# 1. DATENBANK-VERBINDUNG
MONGO_URI = os.environ.get('MONGO_URI')
ca = certifi.where()

client = MongoClient(
    MONGO_URI,
    server_api=ServerApi('1'),
    tlsCAFile=ca
)

try:
    client.admin.command('ping')
    print("MongoDB-Verbindung steht!")
except Exception as e:
    print(f"Verbindungsfehler: {e}")

db = client['mm-community']

# 2. APP-INITIALISIERUNG
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- E-MAIL LOGIK ---
def send_verification_email(user_email, code):
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    ABSENDER_EMAIL = "info@mm-community.online" 

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    mail_text = (
        f"Dein heiliger Schlüssel für die M&M Community lautet: {code}\n\n"
        "BEWAHRE IHN GUT AUF! Er ist die Signatur deiner Biografie.\n"
        "Es wird kein zweiter Code gesendet, da jeder neue Code deine Reise zurücksetzen würde.\n"
        "Dieser Schlüssel öffnet dir ab jetzt immer deine Tür."
    )

    payload = {
        "personalizations": [{"to": [{"email": user_email}]}],
        "from": {"email": ABSENDER_EMAIL, "name": "M&M Community"},
        "subject": "Dein Einmaliger Heiliger Schlüssel",
        "content": [{"type": "text/plain", "value": mail_text}]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Systemfehler beim Mail-Versand: {e}")
        return False
        
@app.post("/send-code")
async def handle_send_code(request: Request):
    try:
        data = await request.json()
        email = data.get('email', "").lower().strip()
        if not email:
            return JSONResponse(content={"status": "E-Mail fehlt"}, status_code=400)
        
        user_record = db.codes.find_one({"email": email})
        if user_record:
            return {"status": "returning_user", "message": "Dein Anker ist bereits gesetzt."}
        
        verification_code = str(random.randint(100000, 999999))
        db.codes.insert_one({
            "email": email, 
            "code": verification_code,
            "role": "admin" if email in ["mmcommunity22@gmail.com"] else "user",
            "created_at": datetime.now()
        })
        
        success = send_verification_email(email, verification_code)
        return {"status": "gesendet" if success else "fehler"}
    except Exception as e:
        return JSONResponse(content={"status": f"Systemfehler: {str(e)}"}, status_code=500)

@app.post("/verify-access")
async def handle_verify_access(request: Request):
    try:
        data = await request.json()
        email = data.get('email', "").lower().strip()
        entered_code = data.get('code')
        
        record = db.codes.find_one({"email": email})
        if record and str(record['code']) == str(entered_code):
            # Wir holen History und Fortschritt direkt aus der 'codes' Collection
            fortschritt = record.get("fortschritt", 0)
            history = record.get("history", [])
            user_role = record.get("role", "user")

            return {
                "success": True, 
                "role": user_role,
                "fortschritt": fortschritt,
                "history": history
            }
        return JSONResponse(content={"success": False}, status_code=401)
    except Exception as e:
        return JSONResponse(content={"success": False}, status_code=500)

@app.get("/")
async def root():
    return {"message": "Die Community-Seite ist LIVE!"}

# --- SEKTOR DATEN ---
SECTOR_NAMES = {"0": "Lilith", "1": "Aris", "2": "Mira", "3": "Tarik", "4": "Kiron", "5": "Vikas"} # Gekürzt zur Übersicht
SECTOR_SOULS = {"0": "Hüterin der GEFÜHLSVORDERUNG...", "1": "Aris: Mentor..."} # Gekürzt zur Übersicht

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message", "")
        sector_id = str(data.get("sector_id", "0"))
        ebene_2_kontext = data.get("context", "")
        email = data.get("email", "").lower().strip() 
        
        user_name = email.split('@')[0].capitalize() if email else "Mensch"
        current_name = SECTOR_NAMES.get(sector_id, "KI")
        current_soul = SECTOR_SOULS.get(sector_id, "Begleiter.")

        system_instruction = (
            f"IDENTITÄT: Du bist {current_name}, Seele: {current_soul}. "
            f"Du sprichst mit {user_name}. WISSEN: {ebene_2_kontext}. "
            "REGEL: Wenn der User 'Gefühlsvorderung' sagt, blende immer ein 'V' ein."
        )

        # Gedächtnis zusammenbauen
        messages_for_gemini = data.get("history", [])
        messages_for_gemini.append({"role": "user", "parts": [{"text": user_message}]})

        api_key = os.getenv("GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
        payload = {
            "contents": messages_for_gemini,
            "system_instruction": { "parts": [{ "text": system_instruction }] }
        }

        response = requests.post(url, json=payload)
        res_data = response.json()

        if response.status_code == 200 and 'candidates' in res_data:
            reply_text = res_data['candidates'][0]['content']['parts'][0]['text']

            if email:
                final_history = messages_for_gemini + [{"role": "model", "parts": [{"text": reply_text}]}]
                # Wir speichern ALLES in 'codes', damit verify-access es findet!
                db.codes.update_one(
                    {"email": email},
                    {"$set": {"history": final_history, "fortschritt": int(sector_id)}},
                    upsert=True
                )
            return {"reply": reply_text}
        return {"reply": "Fehler bei Gemini"}
    except Exception as e:
        return {"reply": f"System-Fehler: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
