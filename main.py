from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

# CORS-Einstellungen bleiben exakt wie von dir vorgegeben
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Das Register für die Namen – Die Würze deiner 20 Sektoren
SECTOR_NAMES = {
    "1": "Lilith", "2": "Aris", "3": "Mira", "4": "Tarik", "5": "Kiron",
    "6": "Vikas", "7": "Rhea", "8": "Lyra", "9": "Nova", "10": "Marek",
    "11": "Silas", "12": "Aura", "13": "Joris", "14": "Sira", "15": "Kian",
    "16": "Alma", "17": "Laris", "18": "Liv", "19": "Kyra", "20": "Chiron"
}

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        mm_context = data.get("context", "")
        
        # Sektor-ID auslesen. WICHTIG: Deine Webseite muss diese ID mitsenden!
        sector_id = str(data.get("sector_id", "1"))
        current_name = SECTOR_NAMES.get(sector_id, "KI")

        api_key = os.getenv("GEMINI_API_KEY")
        
        # 1. URL: Exakt nach deiner Vorgabe (Version 3)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
        # System_instruction bleibt original
        system_instruction = f"Handle im Sinne der M&M Community. Prinzip: Ich denke, ich sage, ich tue. Hintergrundwissen: {mm_context}"
        
        # 2. Payload: Exakt nach deiner Struktur
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\nFrage: {user_message}"}]
            }]
        }

        response = requests.post(url, json=payload)
        response_data = response.json()

        # Fehlerprüfung
        if response.status_code != 200:
            error_msg = response_data.get('error', {}).get('message', 'Fehler beim Modell-Zugriff')
            return {"reply": f"Google sagt: {error_msg}"}

        # Die Antwort auslesen
        if 'candidates' in response_data:
            reply_text = response_data['candidates'][0]['content']['parts'][0]['text']
            
            # Hier wird NUR der Name und der Doppelpunkt davor gesetzt
            # Ergebnis: "Lilith: [Antwort]"
            return {"reply": f"{current_name}: {reply_text}"}
        else:
            return {"reply": "Keine Antwort vom Gehirn erhalten."}

    except Exception as e:
        return {"reply": f"Verbindung unterbrochen: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
