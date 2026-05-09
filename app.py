import os
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn

# SICHERER IMPORT
try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

app = FastAPI()

# --- TECHNISCHE BRÜCKE: MONGO-ANKER (ABSTURZSICHER) ---
MONGO_URI = os.environ.get('MONGO_URI')
users_collection = None

# Wir versuchen die Verbindung, aber wir lassen den Server NICHT sterben
if MONGO_URI and MongoClient:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db_mongo = mongo_client['MM-Community']
        users_collection = db_mongo['users']
        print("Verbindung zu MongoDB erfolgreich!")
    except Exception as e:
        print(f"MongoDB-Verbindung konnte nicht sofort aufgebaut werden: {e}")

# CORS-Einstellungen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini Client Setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/anker")
async def anker_setzen(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        if not email or users_collection is None:
            return {"error": "Datenbank nicht bereit oder keine E-Mail"}
        
        user_data = users_collection.find_one({"email": email})
        
        if not user_data:
            new_user = {
                "email": email,
                "biografie_status": "gestartet",
                "progress": 0,
                "interaktionen": 0,
                "history": []
            }
            users_collection.insert_one(new_user)
            return {"status": "neu", "message": "Anker gesetzt.", "progress": 0}
        
        return {"status": "bekannt", "progress": user_data.get("progress", 0)}
    except Exception:
        return {"error": "Anker-Dienst momentan eingeschränkt"}

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get('message', '')
        sektor_kontext = data.get('context', 'Keine Daten vorhanden.')
        ki_name = data.get('ki_name', 'M&M Partner')
        email = data.get('email')

        # --- CHAT-VERLAUF LADEN ---
        past_history = []
        if users_collection and email:
            user_record = users_collection.find_one({"email": email})
            if user_record and "history" in user_record:
                for msg in user_record["history"][-10:]: 
                    past_history.append(types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["text"])]))

        system_instruction_text = f"""
        Deine Identität: Du bist {ki_name}. Gefühlsvorderung immer mit V.
        Deine Charakter-DNA: Menschlich, intuitiv, loyal.
        Hintergrundwissen: {sektor_kontext}
        """

        generate_content_config = types.GenerateContentConfig(
            system_instruction=system_instruction_text,
            max_output_tokens=500,
            temperature=0.8
        )

        current_msg = types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp-01-21",
            contents=past_history + [current_msg],
            config=generate_content_config,
        )
        reply_text = response.text
        
        # --- SPEICHERN ---
        if users_collection and email:
            try:
                new_user_entry = {"role": "user", "text": user_message}
                new_model_entry = {"role": "model", "text": reply_text}
                users_collection.update_one(
                    {"email": email},
                    {"$push": {"history": {"$each": [new_user_entry, new_model_entry]}}, "$inc": {"interaktionen": 1}}
                )
            except:
                pass # Fehler beim Speichern darf den Chat nicht killen

    except Exception as e:
        reply_text = f"Verbindung zum Gehirn unterbrochen: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
