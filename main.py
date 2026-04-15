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
        mm_context = data.get("context", "")

        api_key = os.getenv("GEMINI_API_KEY")
        
        # 1. KORREKTUR: Die URL exakt nach deinem Foto (Version 3)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
        system_instruction = f"Handle im Sinne der M&M Community. Prinzip: Ich denke, ich sage, ich tue. Hintergrundwissen: {mm_context}"
        
        # 2. KORREKTUR: Die Struktur (Payload) angepasst an Gemini 3
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
            return {"reply": reply_text}
        else:
            return {"reply": "Keine Antwort vom Gehirn erhalten."}

    except Exception as e:
        return {"reply": f"Verbindung unterbrochen: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
