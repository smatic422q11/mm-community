from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

app = FastAPI()

# Das hier ist der Türsteher, der alles erlaubt:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    # Hier kommt deine KI Logik rein
    return {"reply": f"Der zahnlose Frosch hat empfangen: {user_message}"}

@app.get("/")
async def root():
    return {"status": "online"}
