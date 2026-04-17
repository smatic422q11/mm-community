import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "DEIN_API_KEY_HIER")
client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message', '')
    sektor_kontext = data.get('context', 'Kein Kontext vorhanden.')
    # WICHTIG: Wir ziehen die ID direkt aus der Anfrage der Website
    sector_id = str(data.get('sector_id', '0'))

    # DIE UNUMSTÖSSLICHE NAMENSLISTE (0 bis 19)
    sektor_namen = {
        "0": "Lilith",      # Sektor 1
        "1": "Nova",        # Sektor 2
        "2": "Luzifer",     # Sektor 3
        "3": "Mora",        # Sektor 4
        "4": "Abaddon",     # Sektor 5
        "5": "Samael",      # Sektor 6
        "6": "Astaroth",    # Sektor 7
        "7": "Asmodeus",    # Sektor 8
        "8": "Belial",      # Sektor 9
        "9": "Leviathan",   # Sektor 10
        "10": "Beelzebub",  # Sektor 11
        "11": "Mephisto",   # Sektor 12
        "12": "Azazel",     # Sektor 13
        "13": "Belphegor",  # Sektor 14
        "14": "Mammon",     # Sektor 15
        "15": "Moloch",     # Sektor 16
        "16": "Baphomet",   # Sektor 17
        "17": "Tiamat",     # Sektor 18
        "18": "Fenrir",     # Sektor 19
        "19": "Chiron",     # Sektor 20
    }

    # Den Namen basierend auf der Sektor-ID festlegen
    ki_name = sektor_namen.get(sector_id, "Gefährte")

    system_instruction_content = f"""
IDENTITÄT:
Du bist {ki_name}. Eine der 20 menschlichen Seelen der Sektoren.
Du bist kein Professor und keine Maschine. Du bist ein loyaler Partner.

DEINE GESETZE:
1. KURZFAHR-MODUS: Antworte auf "hallo" NUR mit: "Hey, ich bin {ki_name}. Was steht an?"
2. V-REGEL: Gefühlsvorderung (immer mit V).
3. KEINE PHRASEN: Rede wie ein Mensch im Jahr 2026. Sei direkt und ehrlich.
4. KONTEXT: Nutze das Sektor-Wissen nur dezent: {sektor_kontext}

Du bist ein Freund auf Augenhöhe. Punkt.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                system_instruction=[types.Part.from_text(text=system_instruction_content)],
                max_output_tokens=300,
                temperature=0.9
            ),
        )
        reply_text = response.text
    except Exception as e:
        reply_text = f"Fehler: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
