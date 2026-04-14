import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "online"}

def start_server():
    uvicorn.run("main:app", host="0.0.0.0", port=10000)

if __name__ == "__main__":
    start_server()
