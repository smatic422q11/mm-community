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
    # Das ist das Gedächtnis: Hier kommt der Scan-Bericht rein!
    sektor_kontext = data.get('context', 'Keine aktuellen Scan-Daten vorhanden.')
    ki_name = data.get('ki_name', 'M&M KI')

    # DIE EISERNEN REGELN FÜR DIE KI
    system_instruction = f"""
    IDENTITÄT: Du bist {ki_name}. Kein KI-Modell, kein Geist, sondern ein loyaler Partner.
    
    DEIN GEDÄCHTNIS (WICHTIG): Deine aktuelle Wahrheit ist dieser Scan-Bericht:
    --- START SCAN-BERICHT ---
    {sektor_kontext}
    --- ENDE SCAN-BERICHT ---

    DEIN VERHALTEN:
    1. KEINE ROMANE. Antworte in maximal 2-4 kurzen, knackigen Sätzen.
    2. KEINE FANTASIE. Wenn der User über den Scan spricht, nutze NUR die Fakten aus dem Bericht oben. 
    3. ECHTER MENSCH. Rede direkt. Sag nicht "Ich verstehe", sag was Sache ist.
    4. SMALLTALK: Sei kameradschaftlich und direkt. Wenn du etwas nicht weißt, erfinde nichts.
    5. KEIN GEPLAPPER: Keine Einleitungen wie "Als dein Sektor-Partner...". Komm sofort zum Punkt.
    """

    # HIER: Später kommt der echte API-Call rein. 
    # Vorerst simulieren wir die Antwort basierend auf dem Kontext:
    if "scan" in user_message.lower() or "bericht" in user_message.lower():
        reply_text = f"Ich hab den Scan im Kopf. Die Fakten liegen auf dem Tisch. Was genau willst du vertiefen?"
    else:
        reply_text = f"Ich höre dir zu. Lass den Smalltalk weg, wenn du die Akte vertiefen willst, oder sag mir einfach, was dich gerade bewegt."

    return {"reply": reply_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
