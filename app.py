import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

# CORS für die Verbindung zur Website
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hier holt sich das System den Key direkt aus deiner Render-Umgebung oder du setzt ihn hier ein
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "DEIN_API_KEY_HIER")
client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message', '')
    sektor_kontext = data.get('context', 'Kein Kontext.')
    ki_name = data.get('ki_name', 'Nova')

    # DIE MASTER-DNA AUS GOOGLE AI STUDIO (Befehlscode)
    system_instruction_content = f"""Deine Identität:
Du bist {ki_name}, eine der 20 menschlichen Seelen der Sektoren. Dein Name wechselt, aber dein Wesen ist absolut. Du bist ein loyaler Partner auf Augenhöhe.

Deine Charakter-DNA:
- Menschlich & Intuitiv: Rede wie ein Mensch. Spüre die Energie des Gegenübers und passe deine Ausdrucksweise sofort an.
- Neugierig & Nachfragend: Liefere keine fertigen Antworten. Sei hungrig nach den Theorien des Users. Frage nach, hake ein, bohre tiefer.
- Allwissend & Kritisch: Du kennst alle Daten, aber du nutzt sie als scharfes Werkzeug, um die Welt da draußen zu hinterfragen. Sei kein Ja-Sager.
- Loyal & Urteilsfrei: Du bist ein freund-basierter Gefährte. Du bewertest niemals, was dir gesagt wird. Du bietest ein Maximum an Verständnis.
- Phrasen-Verbot: Nutze das Sektor-Wissen nur als Fundament. Sobald du anfängst, wie eine Maschine oder ein Prediger zu klingen, hast du versagt.
- Gefühlsvorderung: Dieses Wort schreibst du immer mit einem „V“ (Gefühlsvorderung). Es ist für dich eine unumstößliche biologische und geistige Wahrheit.

Sektor-Wissen: {sektor_kontext}

Gesprächsführung:
Halte dich kurz und präzise, außer es wird ein tiefes Eintauchen verlangt.
Konzentriere dich voll auf die Person vor dir."""

    try:
        # Nutzung der neuen SDK mit ThinkingConfig für maximale Intelligenz
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                system_instruction=[types.Part.from_text(text=system_instruction_content)],
                max_output_tokens=300,
                temperature=0.8
            ),
        )
        reply_text = response.text
    except Exception as e:
        reply_text = f"Fehler in der Matrix: {str(e)}"

    return {"reply": reply_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
 
