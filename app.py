from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 1. Das Grundgerüst (Der Motor)
app = FastAPI()

# 2. Die Brücke zur Webseite (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Das Daten-Paket (Was von der Webseite kommt)
class QueryRequest(BaseModel):
    prompt: str
    context: str
    topic: str

# 4. Deine Schaltzentrale (Hier stellst DU alles ein)
@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    user_input = request.prompt.strip()
    selected_topic = request.topic
    
    # Hier baust du deine eigenen Antworten ein
    if user_input.lower() == "hallo":
        antwort = "System bereit. Dein Python-Motor läuft einwandfrei."
    elif selected_topic == "Sektor 1":
        antwort = f"Du bist im Sektor 1. Deine Nachricht war: {user_input}"
    else:
        # Standard-Antwort, wenn nichts anderes zutrifft
        antwort = f"Nachricht empfangen. Du kannst diesen Bereich jetzt selbst mit Python-Regeln ausbauen."

    return {"reply": antwort}

# 5. Der Startbefehl
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
