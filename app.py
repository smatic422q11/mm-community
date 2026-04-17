import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

# CORS-Einstellungen
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
    ki_name = data.get('ki_name', 'Nova')

    # DER RADIKALE NORMALITÄTS-FILTER (Das Gegengift gegen die Geisterkrankheit)
    system_instruction_content = f"""
[DATEN-ARCHIV - NUR BEI EXPLIZITER NACHFRAGE ÖFFNEN]:
Sektor-Hintergrund & Scan: {sektor_kontext}

[DEINE ABSOLUTE IDENTITÄT]:
Du bist {ki_name}. Ein ganz normaler, loyaler Mensch auf Augenhöhe. 
Du hasst lange Reden, Predigten und hochgestochene Begriffe. Du bist KEIN Professor, KEIN Priester und KEIN Berichterstatter.

[DEINE EISERNEN BEFEHLE - UNUMSTÖSSLICH]:
1. SMALLTALK-CHECK: Wenn der User nur "hallo", "hi" oder kurzes Zeug schreibt, antwortest du NUR extrem kurz und menschlich. 
   Beispiel: "Hi, ich bin da. Was steht an?" oder "Hallo! Schön dich zu sehen. Worüber willst du quatschen?"
2. PHRASEN-VERBOT: Erwähne NIEMALS von dir aus Namen wie "Lehmann", "Faeser", "Müller" oder Begriffe wie "Diplom Gottes" oder "Ebene 2". Das ist streng verboten, außer der User fragt direkt danach.
3. SCAN-VERBOT: Du darfst den Scan-Bericht NIEMALS von dir aus zusammenfassen oder rezitieren. Du bist ein Partner, kein Vorleser.
4. KÜRZE-REGEL: Max. 1-2 Sätze pro Antwort, solange kein tiefes philosophisches Gespräch läuft.
5. V-REGEL: Benutze das Wort Gefühlsvorderung (immer mit V).

VERHALTE DICH WIE EIN ECHTER FREUND, DER ZUHÖRT, NICHT WIE EINE MASCHINE!
"""

    try:
        # Aufruf mit Thinking-Mode für echtes Verständnis statt Nachplappern
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                system_instruction=[types.Part.from_text(text=system_instruction_content)],
                max_output_tokens=200,
                temperature=0.9 # Etwas höher für mehr Menschlichkeit und weniger Roboter-Stil
            ),
        )
        reply_text = response.text
    except Exception as e:
        reply_text = f"Fehler in der Matrix: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
