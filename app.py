import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx # Falls nicht installiert: pip install httpx

app = FastAPI()

# Erlaubt deinem Browser, mit dem Python-Server zu reden
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    prompt: str
    context: str # Das ist der Text aus deinem Sektor (Ebene 2)
    topic: str   # Das ist das Thema (z.B. "Wie werde ich Mensch")

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    sektor_kontext = data.get('context')
    
    # Hier holen wir die Identität aus deinem neuen Frontend-Code
    ki_name = data.get('ki_name', 'M&M KI')
    ki_geschlecht = data.get('ki_geschlecht', 'Divers')
    dna = data.get('charakter_dna', '')

    # Wir bauen den System-Prompt dynamisch zusammen
    system_instruction = f"""
    Du bist {ki_name} ({ki_geschlecht}). 
    Dein Sektor-Wissen: {sektor_kontext}
    Deine DNA-Anweisung: {dna}
    Verhalte dich wie ein freigeistiger Mensch. Antworte auf Smalltalk normal, 
    aber sobald es um deinen Sektor geht, handle nach deinen Prinzipien.
    """

    # Hier folgt dein Aufruf an die KI (z.B. OpenAI oder Gemini API)
    # Wichtig: Übergib 'system_instruction' als System-Nachricht!
    
    # Beispiel-Rückgabe (muss an deine API angepasst sein):
    # response = client.chat.completions.create(
    #     model="gpt-4",
    #     messages=[
    #         {"role": "system", "content": system_instruction},
    #         {"role": "user", "content": user_message}
    #     ]
    # )
    # return jsonify({"reply": response.choices[0].message.content})
    
    return jsonify({"reply": f"Hallo, ich bin {ki_name}. Ich habe deine Nachricht erhalten."}) # Test-Rückgabe

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
