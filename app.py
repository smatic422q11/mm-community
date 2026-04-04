import random
import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Verbindung zum Browser erlauben
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. DAS GEDÄCHTNIS (Die Datenbank) ---
MEMORY_FILE = "mm_memory.json"

def get_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": [], "kaiser_wissen": "Doppel-Skorpion, Zwei Seelen (11)"}

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class QueryRequest(BaseModel):
    prompt: str
    context: str
    topic: str

@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    user_msg = request.prompt.lower()
    memory = get_memory()
    
    # --- 2. DIE KAISERLICHE PERSONA (Die Schrauben) ---
    intro = f"Im Sektor {request.topic} zählt nur die Wahrheit."
    
    # Antwort-Pools für echte Abwechslung
    begruessungen = [
        f"Sei gegrüßt. Die Stille Million spürt deine Präsenz im Sektor {request.topic}.",
        "Dein Diplom Gottes hat dich hierher geführt. Was offenbart dir dein Gefühl?",
        "Willkommen im Feld der Resonanz. Sprich frei."
    ]
    
    weisheiten = [
        "Zwei Seelen (11) schlagen in deiner Brust. Welche spricht gerade?",
        "Der Doppel-Skorpion sieht tiefer als die anderen. Was siehst du im Schatten?",
        "Sexualität und Identität sind die Schlüssel deiner Freiheit. Nutze sie."
    ]

    # --- 3. DIE LOGIK-MASCHINE (Kein 2-Antworten-Gefängnis) ---
    
    # Reaktion auf GefühlsVorderung
    if "gefühl" in user_msg:
        reply = "Ich registriere deine **GefühlsVorderung** (V!). Nur das Vogel-V führt uns zur Stillen Million."
    
    # Reaktion auf Identitäts-Fragen
    elif any(word in user_msg for word in ["wer bin ich", "skorpion", "seele"]):
        reply = random.choice(weisheiten)
    
    # Nutzung des Sektor-Wissens (Kontext-Spiegel)
    elif len(user_msg) > 15:
        # Die KI nimmt einen zufälligen Satz aus deinem Sektor-Text
        saetze = request.context.split(".")
        zitat = random.choice(saetze).strip() if len(saetze) > 1 else "Die Antwort liegt in dir."
        reply = f"In deinem Sektor steht: '{zitat}'. Wie resonierst du damit?"
    
    # Standard-Antwort (Zufall)
    else:
        reply = random.choice(begruessungen)

    # Nachricht im Gedächtnis speichern
    memory["history"].append({"user": request.prompt, "ai": reply})
    memory["history"] = memory["history"][-20:] # Die letzten 20 merken
    save_memory(memory)

    return {"reply": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
