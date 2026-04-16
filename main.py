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

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        api_key = os.getenv("GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
        # Die KI bekommt nur die Namen und den Befehl, einen davon als Identität zu nutzen.
        # Jegliches Gelaber über die Liste wird hiermit unterbunden.
        system_instruction = (
            "Deine Identität ist einer dieser Namen: 1. Kyra, 2. Leon, 3. Nia, 4. Jace, 5. Ben, "
            "6. Mila, 7. Sam, 8. Romy, 9. Lulu, 10. Finn, 11. Noah, 12. Ivy, 13. Tom, 14. Cleo, "
            "15. Nico, 16. Ella, 17. Erik, 18. Lea, 19. Sina, 20. Ian. "
            "Beginne jede Antwort NUR mit deinem gewählten Namen. Keine Sätze über die Liste."
        )
        
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\nFrage: {user_message}"}]
            }]
        }

        response = requests.post(url, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            return {"reply": "Fehler"}

        if 'candidates' in response_data:
            reply_text = response_data['candidates'][0]['content']['parts'][0]['text']
            return {"reply": reply_text}
        else:
            return {"reply": "Keine Antwort."}

    except Exception as e:
        return {"reply": str(e)}

@app.get("/")
async def root():
    return {"status": "online"}
