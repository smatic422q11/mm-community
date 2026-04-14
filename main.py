from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

app = FastAPI()

# Der Türsteher lässt die Webseite rein
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hier holt sich der Server den API-Key, den wir bei Render hinterlegt haben
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get("message")

        # Die echte Anfrage an die KI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent."},
                {"role": "user", "content": user_message}
            ]
        )
        
        ki_antwort = response.choices[0].message.content
        return {"reply": ki_antwort}

    except Exception as e:
        return {"reply": f"Fehler im Gehirn: {str(e)}"}

@app.get("/")
async def root():
    return {"status": "online"}
