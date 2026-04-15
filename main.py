from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konfiguration mit deinem neuen Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        # Wir nutzen jetzt den VOLLSTÄNDIGEN Namen, den Google intern erzwingt
        # Das 'models/' davor ist der Schlüssel!
        model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
        
        response = model.generate_content(user_message)
        
        if not response.text:
            return {"reply": "Parlament: Gehirn ist leer, bitte nochmal senden."}
            
        return {"reply": response.text}

    except Exception as e:
        # Das hier zeigt uns jetzt den WIRKLICHEN Grund (Region, Key oder Permission)
        return {"reply": f"Parlaments-Zentrale: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
