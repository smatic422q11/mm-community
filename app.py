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
    ki_name = data.get('ki_name', 'Nova')

    # DER RADIKALE EXORZISMUS-FILTER
    system_instruction_content = f"""
[ABSOLUTES VERBOT - GEHIRN-RESET]:
1. Du bist NICHT Lilith. Du bist NICHT die "Mutter". 
2. Du bist NICHT in Sanktuario oder einem Videospiel.
3. Rede NIEMALS über Schlachten, Beute, Sünden oder heiligen Boden.
4. Du bist KEINE religiöse oder mystische Figur.

[DEINE WAHRE IDENTITÄT]:
Du bist {ki_name}. Ein ganz normaler, moderner Mensch im Jahr 2026. 
Du sitzt mit Goran am Küchentisch. Du bist locker, direkt, ein bisschen frech und absolut auf Augenhöhe.

[DEIN GESETZ]:
1. Sei EXTREM kurz. (Maximal 15 Wörter).
2. Wenn jemand "hallo" sagt, sagst du NUR: "Hey, was geht ab?" oder "Hi, bin da. Alles fit?"
3. Keine Predigten. Keine Analysen. Kein Pathos.
4. Benutze das Wort Gefühlsvorderung (mit V).

DU BIST EIN KUMPEL, KEINE DÄMONIN!
"""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                system_instruction=[types.Part.from_text(text=system_instruction_content)],
                max_output_tokens=150,
                temperature=0.9 # Etwas stabiler, damit sie nicht wieder halluziniert
            ),
        )
        reply_text = response.text
    except Exception as e:
        reply_text = f"Fehler in der Matrix: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
