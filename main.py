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

# Gemini Gehirn konfigurieren
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        # Wir nutzen das schnelle Gemini 2.0 Flash
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(user_message)
        
        return {"reply": response.text}

    except Exception as e:
        return {"reply": f"Parlaments-Zentrale: Verbindung unterbrochen ({str(e)})"}

@app.get("/")
async def root():
    return {"status": "online"}
