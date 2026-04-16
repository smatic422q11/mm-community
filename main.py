from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from google import genai
from google.genai import types

app = FastAPI()

# CORS Einstellungen, damit deine Website zugreifen kann
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Verbindung zum Google Client
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
)

# Die festen Instruktionen aus deinem AI Studio
SYSTEM_RULES = """
8 Merkmale (DNA):
Identität
Charakter
Prinzip
Weltbild
Haltung
Kommunikation
Seele
Tabu

Sektor-Zuweisung:
Sektor 1: Kyra (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 2: Leon (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 3: Nia (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 4: Jace (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 5: Ben (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 6: Mila (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 7: Sam (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 8: Romy (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 9: Lulu (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 10: Finn (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 11: Noah (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 12: Ivy (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 13: Tom (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 14: Cleo (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 15: Nico (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 16: Ella (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 17: Erik (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 18: Lea (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 19: Sina (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
Sektor 20: Ian (Identität, Charakter, Prinzip, Weltbild, Haltung, Kommunikation, Seele, Tabu)
"""

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        
        # Konfiguration für das Modell (inklusive Thinking Level HIGH)
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            system_instruction=SYSTEM_RULES
        )

        # Anfrage an Gemini
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_message,
            config=config
        )

        return {"reply": response.text}

    except Exception as e:
        return {"reply": f"Fehler: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
