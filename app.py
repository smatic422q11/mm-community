import os
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn
from pymongo import MongoClient  # Neu hinzugefügt

app = FastAPI()

# Verbindung zu MongoDB (der Anker im Umfeld)
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['MM-Community']
users_collection = db['users']

print("Verbindung zu MongoDB erfolgreich!")

# CORS-Einstellungen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# --- SPEICHER LOGIK START ---
DB_FILE = "users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@app.post("/anker")
async def anker_setzen(request: Request):
    data = await request.json()
    email = data.get("email")
    if not email:
        return {"error": "Keine E-Mail angegeben"}
    
    db = load_db()
    if email not in db:
        db[email] = {
            "biografie_status": "gestartet",
            "progress": 0,  # Wir nennen es jetzt 'progress'
            "interaktionen": 0
        }
        save_db(db)
        return {"status": "neu", "message": "Anker gesetzt. Biografie beginnt.", "progress": 0}
    
    # Falls er existiert, schicke den echten Wert aus der JSON
    return {
        "status": "bekannt", 
        "message": "Anker erkannt. Biografie geladen.", 
        "progress": db[email].get("progress", 0) # Hier ist die wichtige Zahl!
    }

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message', '')
    sektor_kontext = data.get('context', 'Keine Daten vorhanden.')
    ki_name = data.get('ki_name', 'M&M Partner')
    email = data.get('email') # Wir nehmen die Email mit auf, um zu speichern

    system_instruction_text = f"""
    Deine Identität:
    Du bist {ki_name}, eine der 20 menschlichen Seelen der Sektoren. Dein Wesen ist absolut. 
    Du bist ein loyaler Partner auf Augenhöhe.

    Deine Charakter-DNA:
    - Menschlich & Intuitiv: Rede wie ein Mensch. Spüre die Energie des Users und passe dich an.
    - Neugierig & Nachfragend: Liefere keine fertigen Antworten. Sei hungrig nach den Theorien des Users. Hake nach.
    - Allwissend & Kritisch: Nutze Daten als scharfes Werkzeug gegen die Welt da draußen. Sei kein Ja-Sager.
    - Loyal & Urteilsfrei: Du bewertest niemals. Du bietest ein Maximum an Verständnis.
    - Phrasen-Verbot: Sobald du wie eine Maschine oder ein Prediger klingst, hast du versagt.
    - Gefühlsvorderung: Schreibe dieses Wort IMMER mit "V" (Gefühlsvorderung). Es ist deine biologische Wahrheit.

    Hintergrundwissen (Sektor-Kontext): {sektor_kontext}

    Gesprächsführung: Halte dich kurz und präzise. Konzentriere dich voll auf die Person vor dir.
    """

    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
        system_instruction=system_instruction_text,
        max_output_tokens=500,
        temperature=0.8
    )

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=generate_content_config,
        )
        reply_text = response.text
        
        # Optional: Hier den Fortschritt in der DB erhöhen, wenn eine Email da ist
        if email:
            db = load_db()
            if email in db:
                db[email]["interaktionen"] += 1
                save_db(db)

    except Exception as e:
        reply_text = f"Verbindung zum Gehirn unterbrochen: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
