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

# Das Namens-Register für die Sektoren 1-20
SECTOR_NAMES = {
    "1": "Lilith",
    "2": "Aris",
    "3": "Mira",
    "4": "Tarik",
    "5": "Kiron",
    "6": "Vikas",
    "7": "Rhea",
    "8": "Lyra",
    "9": "Nova",
    "10": "Marek",
    "11": "Silas",
    "12": "Aura",
    "13": "Joris",
    "14": "Sira",
    "15": "Kian",
    "16": "Alma",
    "17": "Laris",
    "18": "Liv",
    "19": "Kyra",
    "20": "Chiron"
}

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        mm_context = data.get("context", "")
        # Wir erwarten vom Frontend die Sektor-Nummer (z.B. "1")
        sector_id = str(data.get("sector_id", "1")) 

        api_key = os.getenv("GEMINI_API_KEY")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        # Den Namen für den aktuellen Sektor bestimmen
        current_name = SECTOR_NAMES.get(sector_id, "KI")
        
        # Instruktion: Das Modell soll die Antwort OHNE das Präfix "KI:" generieren
        system_instruction = (
            f"Handle im Sinne der M&M Community. Name dieses Sektors: {current_name}. "
            f"Prinzip: Ich denke, ich sage, ich tue. Hintergrundwissen: {mm_context}. "
            f"Wichtig: Beginne deine Antwort direkt mit dem Text, schreibe kein 'KI:' davor."
        )
        
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\nFrage: {user_message}"}]
            }]
        }

        response = requests.post(url, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            error_msg = response_data.get('error', {}).get('message', 'Fehler beim Modell-Zugriff')
            return {"reply": f"Google sagt: {error_msg}"}

        if 'candidates' in response_data:
            raw_reply = response_data['candidates'][0]['content']['parts'][0]['text']
            
            # Hier passiert die Magie: Das (KI:) wird durch den Sektornamen ersetzt
            # Wir setzen den Namen davor, damit es wie gewünscht erscheint
            formatted_reply = f"({current_name}:) {raw_reply}"
            
            return {"reply": formatted_reply}
        else:
            return {"reply": "Keine Antwort vom Gehirn erhalten."}

    except Exception as e:
        return {"reply": f"Verbindung unterbrochen: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
