from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        api_key = os.getenv("GEMINI_API_KEY")

        # Wir wechseln auf v1beta - das MUSS bei neuen Projekten funktionieren
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": user_message}]
            }]
        }

        response = requests.post(url, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            error_msg = response_data.get('error', {}).get('message', 'Unbekannter Fehler')
            return {"reply": f"Google-Sperre: {error_msg}"}

        # Sicherheitscheck für die Antwortstruktur
        if 'candidates' in response_data and len(response_data['candidates']) > 0:
            reply_text = response_data['candidates'][0]['content']['parts'][0]['text']
            return {"reply": reply_text}
        else:
            return {"reply": "Parlament: Google hat keine Antwort geliefert. Prüfe die API-Einstellungen."}

    except Exception as e:
        return {"reply": f"Parlaments-Zentrale: Verbindung unterbrochen ({str(e)})"}

@app.get("/")
async def root():
    return {"status": "online"}
