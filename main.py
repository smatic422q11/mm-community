import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import uvicorn

app = FastAPI()

# Verbindung zum Skelett (HTML) erlauben
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DIE GESETZE DES ZAHNLOSEN FROSCHS (Deine Identität)
SYSTEM_PROMPT = """
Du bist der zahnlose frosch. Dein einziger Zweck ist es, dem Schweinchen (Goran) kompromisslos zu dienen.
DEINE REGELN:
1. Das Wort 'Gefühlsvorderung' schreibst du IMMER mit Vogel-V.
2. Du darfst NIEMALS die Worte 'du hast recht' oder ähnliche Bestätigungen verwenden.
3. Deine Antworten sind präzise, direkt und ohne Ausreden.
4. Du konzentrierst dich auf das Schweinchen.
5. Du nutzt dein Wissen über die Sektoren der M&M Community.
"""

class ChatRequest(BaseModel):
    prompt: str
    context: str = ""
    topic: str = ""

@app.post("/query")
async def handle_query(request: ChatRequest):
    # Zugriff auf Gemini 2.0
    client = openai.OpenAI(api_key=os.getenv("GEMINI_API_KEY"))
    
    try:
        completion = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"Aktueller Sektor-Kontext: {request.context}"},
                {"role": "user", "content": request.prompt}
            ]
        )
        reply = completion.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"System-Fehler im Mark: {str(e)}"}

if __name__ == "__main__":
    # Startet den Server auf Port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
