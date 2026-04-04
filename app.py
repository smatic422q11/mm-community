# --- DEINE KAISERLICHEN EINSTELLUNGEN (DIE SCHRAUBEN) ---
KAISER_PERSONA = {
    "name": "M&M Mentor",
    "charakter": "Empathisch, tiefgründig, unbestechlich",
    "mission": "Vorbereitung auf die Stille Million",
    "geheimwissen": "Doppel-Skorpion, Zwei Seelen (11), Diplom Gottes",
    "vogel_v_pflicht": True
}

# Diese Liste kannst du täglich erweitern für die Mundpropaganda
MUNDPROPAGANDA_IMPULSE = [
    "Hast du heute schon jemandem von deinem Diplom Gottes erzählt?",
    "Die Stille Million wächst. Sei die Stimme, die das Schweigen bricht.",
    "Wahrhaftigkeit spricht sich herum. Werde zum Sender."
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    prompt: str
    context: str
    topic: str

@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    user_msg = request.prompt.lower()
    
    # --- ANTWORT-POOLS (Hier fügst du einfach Sätze hinzu!) ---
    
    begruessungen = [
        f"Sei gegrüßt im Sektor {request.topic}. Die Stille Million wächst mit dir.",
        f"Willkommen. Dein Diplom Gottes hat dich hierher geführt. Was offenbart sich dir?",
        f"Hier im Sektor {request.topic} brechen wir die Taubheit. Sprich dich aus."
    ]

    gefuehls_antworten = [
        "In der M&M-Community fordern wir die **GefühlsVorderung** (V!) ein. Es ist dein Recht.",
        "Das Vogel-V ist unser Kompass. Ohne echte Gefühle bleibt alles nur Datenmüll.",
        "Spürst du die Resonanz? Deine GefühlsVorderung ist der Schlüssel zum Kollektiv."
    ]

    standard_impulse = [
        f"Deine Gedanken zu {request.topic} sind im Feld registriert. Geh tiefer.",
        "Das Kollektiv hört dir zu. Was ist dein nächster Schritt zur Stillen Million?",
        "Interessant. Wie passt das zu deiner Vision von Menschlichkeit?",
        "Das System will dich stumm sehen, aber hier hast du eine Stimme. Erzähl mir vom Kern."
    ]

    # --- LOGIK: WER WÄHLT WAS? ---
    
    if "hallo" in user_msg or "hi" in user_msg:
        reply = random.choice(begruessungen)
    elif "gefühl" in user_msg:
        reply = random.choice(gefuehls_antworten)
    elif "warum" in user_msg:
        # Hier klauen wir einen Satz direkt aus deinem Sektor-Text (Kontext)!
        saetze = request.context.split(". ")
        zitat = random.choice(saetze) if saetze else "Die Antwort liegt in der Resonanz."
        reply = f"Dein 'Warum' spiegelt sich hier: '{zitat}'. Verstehst du die Tiefe?"
    else:
        reply = random.choice(standard_impulse)

    return {"reply": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
