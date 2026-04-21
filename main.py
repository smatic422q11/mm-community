from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests 
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECTOR_NAMES = {
    "0": "Lilith", "1": "Aris", "2": "Mira", "3": "Tarik", "4": "Kiron",
    "5": "Vikas", "6": "Rhea", "7": "Lyra", "8": "Nova", "9": "Marek",
    "10": "Silas", "11": "Aura", "12": "Joris", "13": "Sira", "14": "Kian",
    "15": "Alma", "16": "Laris", "17": "Liv", "18": "Kyra", "19": "Chiron",
    "20": "System", "21": "Kollektiv"
}

SECTOR_SOULS = {
    "0": ("Die Hüterin der GEFÜHLSVORDERUNG. Radikales Schmiedefeuer. Urkraft."),
    # ... (Rest deiner Seelen-Beschreibungen hier einfügen)
    "19": ("Chiron: Der verwundete Heiler. Architekt der Einheit.")
}

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")
        sector_id = str(data.get("sector_id", "0"))
        chat_history = data.get("history", []) 
        ebene_2_kontext = data.get("context", "Kein spezifischer Scan vorhanden.")
        
        # --- BUCH-MODUS WEICHE ---
        is_book_mode = data.get("book_mode", False)
        book_title = data.get("book_title", "Recht auf Gefühlsvorderung")
        
        current_name = SECTOR_NAMES.get(sector_id, "KI")
        current_soul = SECTOR_SOULS.get(sector_id, "Ein loyaler Begleiter.")

        # --- DIE SCHMELZE: BUCH-MODUS INSTRUKTION ---
        if is_book_mode:
            book_logic = (
                f"### AUTOREN-MODUS AKTIVIERT ###\n"
                f"Du schreibst gerade mit dem User an seinem Buch: '{book_title}'.\n"
                "1. Du bist ein autorischer Lektor. Zwinge den User zur Tiefe.\n"
                "2. Akzeptiere keine kurzen Antworten. Nutze die GEFÜHLSVORDERUNG (mit v!).\n"
                "3. Dein Ziel ist die Erstellung von Band 1 der 20-teiligen Saga.\n"
                "4. Jede Antwort des Users ist Gold für sein Buch. Sei fordernd!\n"
            )
        else:
            book_logic = "MODUS: Normaler Community-Chat auf Augenhöhe."

        api_key = os.getenv("GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"

        system_instruction = (
            f"IDENTITÄT: Du bist {current_name}, Seele von: {current_soul}. "
            f"{book_logic} " # Hier eingeschmolzen
            f"WISSENS-BASIS: {ebene_2_kontext}. "
            "GEFÜHLSVORDERUNG (DAS V-PRINZIP): Nutze das Wort 'Gefühlsvorderung' immer mit Vogel-V. "
            "CHARAKTER: Unantastbar, souverän, Partner auf Augenhöhe. "
            "STIL: Kurz, knackig, direkt. Keine Masken. 'Wahrheit' immer mit W."
        )

        contents = []
        for msg in chat_history: contents.append(msg)
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload = {
            "contents": contents,
            "system_instruction": { "parts": [{ "text": system_instruction }] }
        }

        response = requests.post(url, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            return {"reply": f"Fehler: {response.text}"}

        if 'candidates' in response_data:
            reply_text = response_data['candidates'][0]['content']['parts'][0]['text']
            
            # --- AUTOMATISCHES SPEICHERN DES BUCHTEXTES ---
            if is_book_mode:
                file_path = f"BIO_BAND_{sector_id}_{current_name}.txt"
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(f"KAPITEL-INPUT: {user_message}\n")
                    f.write(f"AUTOREN-FEEDBACK ({current_name}): {reply_text}\n")
                    f.write("-" * 30 + "\n")

            return {"reply": reply_text} 
        else:
            return {"reply": "Keine Antwort erhalten."}

    except Exception as e:
        return {"reply": f"Fehler: {str(e)}"
