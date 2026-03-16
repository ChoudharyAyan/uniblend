from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from routers import spotify, ytmusic, blend

app = FastAPI(title="UniBlend API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spotify.router, tags=["spotify"])
app.include_router(ytmusic.router, tags=["ytmusic"])
app.include_router(blend.router, tags=["blend"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
