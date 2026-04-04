from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Erlaubt deiner Webseite (Frontend), mit diesem Server zu sprechen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    prompt: str
    context: str
    topic: str

@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    # Hier definieren wir die Identität der KI
    system_instruction = f"""
    Du bist der M&M-Community-Expert. 
    Dein Wissen basiert auf dem Thema: {request.topic}.
    Nutze diesen Sektor-Text als deine absolute Wahrheit: {request.context}
    
    Regeln:
    1. Antworte tiefgründig, philosophisch und empathisch.
    2. Wenn der Nutzer "Gefühlsvorderung" schreibt, achte auf das Vogel-V.
    3. Erinnere den Nutzer an sein 'Diplom Gottes' und seine Eigenverantwortung.
    4. Antworte kurz, aber prägnant (max. 3-4 Sätze).
    """
    
    # HIER: Verbindung zu deinem lokalen Modell oder API (z.B. Claude/Gemini)
    # Für den ersten Test geben wir eine strukturierte Antwort zurück:
    ai_reply = f"In Bezug auf '{request.topic}' und dein 'Diplom Gottes': Deine Nachricht '{request.prompt}' zeigt mir, dass du bereit bist, die Taubheit zu durchbrechen. Wie fühlt sich dieser Aufbruch für dich an?"
    
    return {"reply": ai_reply}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000
