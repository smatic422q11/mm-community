from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# WICHTIG: Das erlaubt deiner Webseite den Zugriff
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
    user_msg = request.prompt.lower()
    
    # --- DEINE LOGIK ---
    if "hallo" in user_msg or "hi" in user_msg:
        reply = f"Sei gegrüßt im Sektor für {request.topic}. Wie kann ich dir heute auf deinem Weg zur Stillen Million helfen?"
    elif "gefühl" in user_msg:
        reply = "In unserer Community fordern wir die **GefühlsVorderung** immer mit Vogel-V. Das ist ein Fundament unserer Wahrhaftigkeit."
    elif "warum" in user_msg:
        reply = "Das Warum liegt in deinem Diplom Gottes. Jedes Wort hier bricht die Schicht aus digitaler Taubheit."
    else:
        reply = f"Ich habe deine Nachricht zu '{request.topic}' empfangen. Deine Resonanz ist wichtig für das Kollektiv. Erzähl mir mehr."
    
    return {"reply": reply}

if __name__ == "__main__":
    # Startet den Server auf Port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
