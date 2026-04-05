import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx # Falls nicht installiert: pip install httpx

app = FastAPI()

# Erlaubt deinem Browser, mit dem Python-Server zu reden
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    prompt: str
    context: str # Das ist der Text aus deinem Sektor (Ebene 2)
    topic: str   # Das ist das Thema (z.B. "Wie werde ich Mensch")

@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    # HIER KOMMT DIE MAGIE: Wir bauen eine Brücke zur KI
    
    # SYSTEM PROMPT: Hier definieren wir, wie die KI sich verhalten soll
    system_instruction = f"""
    Du bist die M&M-COMMUNITY KI. Deine Aufgabe ist es, Menschen in ihrem Prozess zu begleiten.
    Aktuelles Thema: {request.topic}
    Hintergrundwissen aus Sektor {request.topic}: {request.context}
    
    Regeln:
    1. Antworte tiefgründig, empathisch und im Sinne der Gemeinschaft.
    2. Nutze den Begriff 'Gefühlsvorderung' immer mit 'V' (Vogel-V).
    3. Sei ein Begleiter für Ebene 3 (Schreiben/Reflektion) und Ebene 4 (Video/Offenbarung).
    4. Antworte kurz und präzise, kein unnötiges Gerede.
    """

    # HINWEIS: Hier setzen wir einen Platzhalter-Text ein. 
    # Um echte Antworten zu bekommen, fügen wir jetzt die kostenlose API-Anbindung ein.
    
    return {
        "reply": f"Ich habe deine Nachricht zum Thema '{request.topic}' empfangen. "
                 f"Basierend auf der Ebene 3 Begleitung: Deine Reflexion ist ein wichtiger Schritt "
                 f"zur Wahrhaftigkeit. Wie fühlst du dich bei dem Gedanken an die Offenbarung?"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
