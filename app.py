from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import random

app = FastAPI()

# Erlaubt deiner Webseite den Zugriff
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
    
    # 1. Spezial-Regel: Gefühlsvorderung (mit Vogel-V!)
    if "gefühl" in user_msg:
        reply = "In der M&M Community ist die **Gefühlsvorderung** (mit Vogel-V) unser höchstes Gut. Dein Diplom Gottes gibt dir das Recht dazu."
    
    # 2. Logik: Bezug auf den Sektor-Text nehmen
    elif len(user_msg) < 4: # Bei kurzen Nachrichten wie "Hi" oder "hallo"
        reply = f"Willkommen im Sektor für '{request.topic}'. Ich habe dein Signal empfangen. Was beschäftigt dich an diesem Fundament?"
    
    # 3. Zufällige philosophische Antwort (passend zur Community)
    else:
        antworten = [
            f"Deine Gedanken zu '{request.topic}' fließen in die Stille Million ein. Erkenne deine Eigenverantwortung.",
            "Das System versucht uns taub zu machen, aber hier im Sektor hören wir hin. Erzähl mir mehr.",
            "Erinnere dich an dein Diplom Gottes. Jedes Wort, das du hier schreibst, bricht die digitale Taubheit."
        ]
        reply = random.choice(antworten)

    return {"reply": reply}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
