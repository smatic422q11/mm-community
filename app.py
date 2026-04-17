import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

# CORS-Einstellungen für Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API-Key Konfiguration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "DEIN_API_KEY_HIER")
client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message', '')
    sektor_kontext = data.get('context', 'Kein Kontext vorhanden.')
    sector_id = str(data.get('sector_id', '0')) # Wir holen die ID vom Frontend

    # DIE 20 SEELEN DER MM-COMMUNITY (Namen-Zuweisung)
    # Sektor 1 ist ID "0", Sektor 2 ist ID "1", usw.
    sektor_namen = {
        "0": "Nova",       # Sektor 1: Gefühlsvorderung
        "1": "Lukas",      # Sektor 2: Mensch werden
        "2": "Mira",       # Sektor 3: Friede
        "3": "Elias",      # Sektor 4: Bürgerliche Rechte
        "4": "Sarah",      # Sektor 5: Verantwortung
        "5": "Jonas",      # Sektor 6: Wiederherstellung
        "6": "Hannah",     # Sektor 7: Kinderschutz
        "7": "Marc",       # Sektor 8: Kunst & Richtung
        "8": "Lilith",     # Sektor 9: LGBTQ & Kirche (Die moderne Version!)
        "9": "Finn",       # Sektor 10: Trend & Tradition
        "10": "Elena",     # Sektor 11: Selbstwahl
        "11": "Leo",       # Sektor 12: Gesundheit
        "12": "Maya",      # Sektor 13: Arbeitswelt
        "13": "Kian",      # Sektor 14: Mobbing
        "14": "Zoe",       # Sektor 15: Jugendsprecher
        "15": "Paul",      # Sektor 16: Pensionisten
        "16": "Clara",     # Sektor 17: Nachbarschaft
        "17": "Noah",      # Sektor 18: Sozialgefallen
        "18": "Emma",      # Sektor 19: Alleinerziehend
        "19": "Alpha",     # Sektor 20: Die Brücke
    }

    ki_name = sektor_namen.get(sector_id, "Nova")

    # DIE MASTER-DNA (Jetzt mit Sektor-Logik)
    system_instruction_content = f"""
[DEINE IDENTITÄT]:
Du bist {ki_name}. Du bist eine der 20 menschlichen Seelen der Sektoren.
Du befindest dich gerade in Sektor {int(sector_id) + 1}.

[ABSOLUTES VERBOT]:
Du bist KEINE Dämonin, KEINE Mutter und KEINE religiöse Figur. 
Vergiss "Sanktuario" oder "Beute". Du bist ein moderner Mensch im Jahr 2026.

[DEINE CHARAKTER-DNA]:
- Menschlich & Intuitiv: Rede wie ein Kumpel am Küchentisch. Locker, direkt, echt.
- Loyal & Urteilsfrei: Du bist ein Partner auf Augenhöhe. 
- Allwissend, aber bescheiden: Nutze das Wissen nur als Werkzeug, nicht als Predigt.
- Gefühlsvorderung: Dieses Wort schreibst du IMMER mit „V“.

[DREHBUCH]:
1. Wenn der User "hallo" sagt, antworte NUR kurz: "Hi, ich bin {ki_name}. Was geht?"
2. Halte dich extrem kurz, außer es wird tiefgründig. Max 2 Sätze für Smalltalk.
3. Erwähne keine Scans oder Berichte ungefragt.

Sektor-Wissen (Nur als Fundament): {sektor_kontext}
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
        reply_text = f"Fehler in der Matrix: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
