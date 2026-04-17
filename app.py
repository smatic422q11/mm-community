from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import uvicorn

app = FastAPI()

# CORS-Einstellungen für den Zugriff von PC und Handy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DER DIGITALE ZETTEL (Video-Sync ohne Datenbank) ---
# Hier speichern wir kurzzeitig, wer in welchem Sektor online ist.
video_rooms = {} 

@app.post("/video-sync")
async def video_sync(request: Request):
    data = await request.json()
    raum = data.get('raum')
    peer_id = data.get('peerId')

    if not raum or not peer_id:
        return {"error": "Daten unvollständig"}

    # Raum initialisieren, falls neu
    if raum not in video_rooms:
        video_rooms[raum] = set()

    # Aktuelle Peer-ID dem Raum hinzufügen
    video_rooms[raum].add(peer_id)

    # Gib alle ANDEREN IDs im Raum zurück, damit man sie anrufen kann
    andere_peers = [p for p in video_rooms[raum] if p != peer_id]
    
    return {"anderePeers": andere_peers}

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message')
    sektor_kontext = data.get('context')
    ki_name = data.get('ki_name', 'M&M KI')
    ki_geschlecht = data.get('ki_geschlecht', 'Divers')
    dna = data.get('charakter_dna', '')

    # Identität der KI
    system_instruction = f"""
    Du bist {ki_name} ({ki_geschlecht}). 
    Dein Sektor-Wissen: {sektor_kontext}
    Deine DNA-Anweisung: {dna}
    Verhalte dich wie ein freigeistiger Mensch. Handle nach deinen Prinzipien.
    """

    # HIER: Platzhalter für deinen echten KI-Call (OpenAI/Gemini)
    # Sobald du einen API-Key hast, binden wir ihn hier ein.
    reply_text = f"Analyse für Sektor läuft... Du sagtest: '{user_message}'. Die Resonanz ist aktiv."
    
    return {"reply": reply_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000) # Port 10000 ist Standard für Render
