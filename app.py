from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message')
    sektor_kontext = data.get('context')
    ki_name = data.get('ki_name', 'M&M KI')
    ki_geschlecht = data.get('ki_geschlecht', 'Divers')
    dna = data.get('charakter_dna', '')

    # Hier wird die Identität für die KI zusammengebaut
    system_instruction = f"""
    Du bist {ki_name} ({ki_geschlecht}). 
    Dein Sektor-Wissen: {sektor_kontext}
    Deine DNA-Anweisung: {dna}
    Verhalte dich wie ein freigeistiger Mensch. Antworte auf Smalltalk normal, 
    aber sobald es um deinen Sektor geht, handle nach deinen Prinzipien.
    """

    # HIER kommt dein API-Call (z.B. OpenAI) rein. 
    # Vorerst geben wir eine Bestätigung zurück:
    reply_text = f"Hallo, hier spricht {ki_name}. Ich habe verstanden, worum es in meinem Sektor geht."
    
    return {"reply": reply_text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
