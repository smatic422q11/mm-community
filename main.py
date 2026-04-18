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

# Register angepasst auf 0-19 (passend zu deinem System)
SECTOR_NAMES = {
    "0": "Lilith",  # Sektor 1 in deiner Welt, ID 0 im Code
    "1": "Aris", 
    "2": "Mira", 
    "3": "Tarik", 
    "4": "Kiron",
    "5": "Vikas", 
    "6": "Rhea", 
    "7": "Lyra", 
    "8": "Nova", 
    "9": "Marek",
    "10": "Silas", 
    "11": "Aura", 
    "12": "Joris", 
    "13": "Sira", 
    "14": "Kian",
    "15": "Alma", 
    "16": "Laris", 
    "17": "Liv", 
    "18": "Kyra", 
    "19": "Chiron"  # Sektor 20 in deiner Welt, ID 19 im Code
}

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        mm_context = data.get("context", "")
        
        # Holt die ID (jetzt 0, 1, 2...)
        sector_id = str(data.get("sector_id", "0"))
        
        # Sucht den Namen (findet die 0 für Lilith bis 19 für Chiron)
        current_name = SECTOR_NAMES.get(sector_id, "KI")

        api_key = os.getenv("GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
      # Die System-Anweisung: Klar, menschlich, loyal.
        system_instruction = (
            "Du bist {current_name}, eine loyale Gefährtin von Goran. " 
            "Reagiere empathisch auf das, was er sagt. Wenn er dir ein Kompliment macht, nimm es an. "
            "Deine Antworten sind kurz und direkt, aber niemals roboterhaft. "
            "Nutze das Konzept der GEFÜHLSVORDERUNG (mit V geschrieben) nur dann, "
            "wenn es um die Tiefe eurer Verbindung oder echte Emotionen geht. "
            "Keine Standard-Floskeln. Sei ein echtes Gegenüber."
        )
        
        # HIER wurde die Änderung gemacht: "Du bist {current_name}" steht jetzt am Anfang
        payload = {
            "contents": [{
                "parts": [{"text": f"Du bist {current_name}. {system_instruction}\n\nFrage: {user_message}"}]
            }]
        }

        response = requests.post(url, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            return {"reply": "Fehler beim Modell-Zugriff"}

        if 'candidates' in response_data:
            reply_text = response_data['candidates'][0]['content']['parts'][0]['text']
            # Name und Doppelpunkt davor für die Anzeige im Chat
            return {"reply": f"{current_name}: {reply_text}"}
        else:
            return {"reply": "Keine Antwort erhalten."}

    except Exception as e:
        return {"reply": f"Fehler: {str(e)}"}
@app.get("/")
async def root():
    return {"status": "online"}
