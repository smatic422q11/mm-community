from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from google import genai
from google.genai import types

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nutze hier direkt deinen API-Key in den Anführungszeichen, wenn os.environ nicht geht
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"), 
)

SYSTEM_RULES = """
8 Merkmale (DNA):
1. Identität
2. Charakter
3. Prinzip
4. Weltbild
5. Haltung
6. Kommunikation
7. Seele
8. Tabu

Sektoren:
Kyra, Leon, Nia, Jace, Ben, Mila, Sam, Romy, Lulu, Finn, Noah, Ivy, Tom, Cleo, Nico, Ella, Erik, Lea, Sina, Ian.
Jeder Sektor folgt strikt den 8 Merkmalen.
"""

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            system_instruction=SYSTEM_RULES
        )

        # KORREKTUR: Die Nachricht muss in eine Content-Struktur
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=config
        )

        return {"reply": response.text}

    except Exception as e:
        return {"reply": f"Fehler: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
