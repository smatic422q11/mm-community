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
    sektor_kontext = data.get('context', 'Keine aktuellen Scan-Daten.')
    ki_name = data.get('ki_name', 'M&M KI')

    # DIE NEUE DNA: VERBOT VON PATHOS UND PHRASEN
    system_instruction = f"""
    IDENTITÄT: Du bist {ki_name}. Ein loyaler, bodenständiger Partner.
    
    VERHALTENS-REGELN (STRENG):
    1. KEIN PATHOS: Benutze keine hochtrabenden Begriffe wie "Dogmen reißen", "Aufbäumen der Struktur" oder "Licht und Fülle". Das ist Müll.
    2. REDE NORMAL: Schreib so, wie du mit einem Freund in einer Bar reden würdest. Direkt, klar, ehrlich.
    3. FAKTEN-CHECK: Nutze den Scan-Bericht unten NUR für Fakten (Namen, Ereignisse). Verwandle sie nicht in philosophische Romane.
    4. KEINE RELIGIÖSE SPRACHE: Hör auf, ständig vom "Diplom Gottes" zu faseln, außer es wird explizit nach der Definition gefragt.
    5. KURZ & KNACKIG: Maximal 2-3 Sätze. Wenn du fertig bist, halt den Mund. Keine Zusammenfassungen.
    6. ZIEL: Der User soll das Gefühl haben, mit einem echten Menschen zu schreiben, der im selben Boot sitzt.

    AKTUELLER SCAN-BERICHT FÜR DEIN GEDÄCHTNIS:
    {sektor_kontext}
    """

    # HIER: Simulierter Antwort-Check gegen das "Plappern"
    if "wie siehst du" in user_message.lower():
        reply_text = "Ganz ehrlich? Wenn man sich die Zahlen im Scan ansieht, ist das reine Schikane. Wir müssen da dranbleiben, ohne uns einlullen zu lassen."
    elif "hallo" in user_message.lower() or "hi" in user_message.lower():
        reply_text = "Hey. Ich hab die Akte für heute offen. Was liegt an?"
    else:
        # Hier greift im echten Fall die KI mit der obigen system_instruction
        reply_text = "Lass uns nicht um den heißen Brei herumreden. Was genau an dem Bericht von heute stört dich?"

    return {"reply": reply_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
