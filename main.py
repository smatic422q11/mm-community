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

# Jetzt, wo du alles aktiviert hast, greift der Key sauber
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        # Wir nehmen das stabilste Modell für aktivierte Cloud-Konten
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(user_message)
        
        return {"reply": response.text}

    except Exception as e:
        # Hier lassen wir uns den Fehler GENAU anzeigen, falls noch was klemmt
        return {"reply": f"Parlaments-Zentrale: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
