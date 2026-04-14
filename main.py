import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# Das erlaubt deiner Webseite, mit dem Render-Server zu sprechen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# So sieht die Nachricht aus, die von der Webseite kommt
class ChatRequest(BaseModel):
    prompt: str
    context: str
    topic: str

@app.get("/")
async def root():
    return {"status": "online"}

@app.post("/query")
async def chat_endpoint(req: ChatRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"reply": "Fehler: Der OpenAI Key fehlt in den Render Settings."}
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Du bist die KI der M&M Community. Kontext: {req.context}. Thema: {req.topic}. Antworte direkt und wahrhaftig."},
                {"role": "user", "content": req.prompt}
            ]
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        return {"reply": f"Technischer Fehler der KI: {str(e)}"}

def start_server():
    uvicorn.run("main:app", host="0.0.0.0", port=10000)

if __name__ == "__main__":
    start_server()
