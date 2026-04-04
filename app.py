import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Sicherheits-Regel für den Browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DATENBANK-ERSATZ: Hier speichern wir das Gedächtnis (B) und das Kollektiv (C)
STORAGE_FILE = "community_memory.json"

def load_memory():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "sectors": {}}

def save_memory(data):
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class QueryRequest(BaseModel):
    prompt: str
    context: str
    topic: str
    username: str = "Gast" # Wir fügen einen Namen hinzu

@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    user_msg = request.prompt.lower()
    memory = load_memory()
    
    # --- A: CHARAKTER-LOGIK (Der Kaiser-Prompt) ---
    # Die KI "weiß" jetzt um die Dualität und die Sexualität
    persona = "Du bist der Mentor der M&M-Community. Du achtest auf die GefühlsVorderung (V!). " \
              "Du kennst die Kraft der zwei Seelen und die Tiefe des Skorpions."

    # --- B: GEDÄCHTNIS (Individuell) ---
    if request.username not in memory["users"]:
        memory["users"][request.username] = {"history": [], "rank": "Suchender"}
    
    # --- C: KOLLEKTIV (Sektor-Speicher) ---
    if request.topic not in memory["sectors"]:
        memory["sectors"][request.topic] = []
    
    # Nachricht zum Sektor-Kollektiv hinzufügen
    new_entry = {"user": request.username, "msg": request.prompt}
    memory["sectors"][request.topic].append(new_entry)
    
    # Nur die letzten 10 Nachrichten behalten, damit es übersichtlich bleibt
    memory["sectors"][request.topic] = memory["sectors"][request.topic][-10:]
    save_memory(memory)

    # --- ANTWORT GENERIEREN ---
    if "gefühl" in user_msg:
        reply = f"In der Resonanz von {request.topic} zählt nur die Wahrheit. Fordere sie ein – mit Vogel-V."
    elif "wer bin ich" in user_msg:
        reply = "Du bist ein Träger des Diploms Gottes, ein Wesen aus zwei Seelen, bereit für die Stille Million."
    else:
        # Hier zeigen wir kurz, was im Kollektiv los ist (C)
        andere = [m["user"] for m in memory["sectors"][request.topic] if m["user"] != request.username]
        kollektiv_info = f" Du bist hier nicht allein. Auch {', '.join(andere[:2])} sind im Feld." if andere else ""
        reply = f"Ich höre dich im Sektor {request.topic}.{kollektiv_info} Was offenbart dir dein inneres Monopol gerade?"

    return {"reply": reply, "history": memory["sectors"][request.topic]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
