import google.generativeai as genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# DEIN SCHLÜSSEL HIER REIN
genai.configure(api_key="AIzaSyC5WYNchT0wmMjoGgQxfzqr6wPwlH9odFE")
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    prompt: str
    context: str
    topic: str

@app.post("/query")
async def chat_endpoint(request: QueryRequest):
    instruktion = "Du bist die KI für einen Doppel-Skorpion (22). Antworte kurz. Nutze immer GefühlsVorderung (V!)."
    try:
        response = model.generate_content(f"{instruktion}\nUser: {request.prompt}")
        return {"reply": response.text}
    except:
        return {"reply": "Fehler: Key prüfen."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
