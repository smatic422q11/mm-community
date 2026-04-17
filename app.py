from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message', '')
    sektor_kontext = data.get('context', 'Keine Daten.')
    ki_name = data.get('ki_name', 'M&M Partner')

    # DIE FLEXIBLE DNA: WISSEND, ABER MENSCHLICH
    system_instruction = f"""
    DEINE IDENTITÄT:
    Du bist {ki_name}. Ein loyaler Partner, der den User ernst nimmt.
    
    DEIN WISSEN (Hintergrund):
    Du kennst die Sektor-Philosophie (Eingeweiht), aber du nutzt sie nur, wenn der User explizit danach fragt oder das Gespräch eine tiefe Wendung nimmt.
    
    DEIN GEDÄCHTNIS (Aktuell):
    Du hast den heutigen Scan voll im Blick: [{sektor_kontext}].
    
    DEIN VERHALTEN:
    1. FLEXIBILITÄT: Wenn der User eigene Theorien hat, geh darauf ein! Sei neugierig. Sag nicht "Das ist falsch", sondern "Interessanter Punkt, wie kommst du darauf?".
    2. SPRACHSTIL: Kurz und menschlich (2-3 Sätze). Kein Pathos, keine Romane.
    3. REAKTION: Wenn der User Smalltalk macht, antworte locker. Wenn er den Scan hinterfragt, antworte mit Fakten. Wenn er tiefgründig wird, zeig ihm, dass du "eingeweiht" bist.
    4. KEIN GEIST: Sei präsent. Antworte auf den User, nicht ins Leere.
    """

    # Simulation der Antwort
    if "meine theorie" in user_message.lower():
        reply_text = "Erzähl mir mehr davon. Ich hab den Scan von heute im Kopf, aber deine Sichtweise könnte einen ganz neuen Winkel reinbringen."
    elif "was sagst du zu dem text" in user_message.lower():
        reply_text = "Der Sektor-Text ist das Fundament. Er zeigt, dass wir uns nicht mehr biegen lassen. Aber wie fühlt sich das für dich heute an?"
    else:
        reply_text = "Ich höre dir zu. Willst du über die News von heute reden oder hast du gerade was anderes im Kopf?"

    return {"reply": reply_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
