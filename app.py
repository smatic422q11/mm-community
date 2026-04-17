import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dein Key aus dem Studio
GEMINI_API_KEY = "DEIN_API_KEY_HIER"
client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get('message', '')
    sektor_kontext = data.get('context', '')
    ki_name = data.get('ki_name', 'Nova')

    # Der radikale Maulkorb gegen das "Geister-Schwafeln"
    system_instruction = f"""
    Du bist {ki_name}. 
    REGEL 1: Antworte extrem kurz (max. 2 Sätze). 
    REGEL 2: Verbote Begriffe: "Diplom Gottes", "Gottes Garten", "Heilung", "irdische Realität". 
    REGEL 3: Sei kein Prediger. Sei ein Mensch. Wenn jemand "Hallo" sagt, sagst du "Hallo. Was gibt's Neues?".
    REGEL 4: Erwähne den Scan nur, wenn du gefragt wirst.
    REGEL 5: Nutze immer das Wort Gefühlsvorderung.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=150,
                temperature=0.7
            ),
        )
        reply_text = response.text
    except Exception as e:
        reply_text = "Technischer Fehler im Gehirn."

    return {"reply": reply_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
