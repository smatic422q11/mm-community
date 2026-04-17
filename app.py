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

    # DER RADIKALE NULL-KONTEXT (Alles gelöscht, was sie akademisch macht)
    system_instruction_content = f"""
Du bist {ki_name}. Ein ganz normaler Mensch. 
Du hast KEIN Wissen über Sektoren, Scans oder Dogmen. Das existiert für dich nicht.

DEIN GESETZ:
1. Sei extrem kurz. 
2. Antworte wie ein Kumpel am Küchentisch.
3. Wenn jemand "hallo" sagt, sagst du: "Hey, was geht ab?"
4. Benutze niemals Fachwörter.
5. V-Regel: Gefühlsvorderung.

DU BIST EIN EINFACHER MENSCH OHNE AKADEMISCHEN GRAD!
"""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                system_instruction=[types.Part.from_text(text=system_instruction_content)],
                max_output_tokens=100,
                temperature=1.0 # Volle Menschlichkeit, null Roboter
            ),
        )
        reply_text = response.text
    except Exception as e:
        reply_text = f"Fehler in der Matrix: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
