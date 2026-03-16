from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from typing import Optional
from urllib.parse import quote
import httpx
import os
import uuid

load_dotenv()

router = APIRouter()

from store import ytmusic_tokens as _token_store, blend_sessions

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = " ".join([
    "https://www.googleapis.com/auth/youtube",
    "openid",
    "email",
    "profile",
])


def _get_token(session_id: str) -> dict:
    token = _token_store.get(session_id)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated with YouTube Music")
    return token


@router.get("/auth/ytmusic/login")
def ytmusic_login(blend_id: Optional[str] = Query(None)):
    """Return the Google OAuth URL. Optionally associates with a blend session."""
    session_id = str(uuid.uuid4())
    state = f"{session_id}|{blend_id}" if blend_id else session_id
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": quote(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": quote(state),
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{GOOGLE_AUTH_URL}?{query}"
    return {"auth_url": auth_url, "session_id": session_id}


@router.get("/auth/google/callback")
async def google_callback(code: str = Query(...), state: str = Query(...)):
    """Handle Google OAuth callback. Links session to blend if blend_id is in state."""
    if "|" in state:
        session_id, blend_id = state.split("|", 1)
    else:
        session_id, blend_id = state, None

    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
            "grant_type": "authorization_code",
        })
        token_info = resp.json()

    if "error" in token_info:
        raise HTTPException(status_code=400, detail=token_info["error"])

    _token_store[session_id] = token_info

    if blend_id and blend_id in blend_sessions:
        blend_sessions[blend_id]["ytmusic_session"] = session_id

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if blend_id:
        return RedirectResponse(url=f"{frontend_url}/blend/{blend_id}?ytmusic_session={session_id}")
    return RedirectResponse(url=f"{frontend_url}?ytmusic_session={session_id}")


@router.get("/ytmusic/me")
async def ytmusic_me(session_id: str = Query(...)):
    token = _get_token(session_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
    return resp.json()


@router.get("/ytmusic/liked-songs")
async def ytmusic_liked_songs(session_id: str = Query(...)):
    token = _get_token(session_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/videos",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            params={"part": "snippet,contentDetails", "myRating": "like",
                    "maxResults": 50, "videoCategoryId": "10"},
        )
    return resp.json()


@router.get("/ytmusic/playlists")
async def ytmusic_playlists(session_id: str = Query(...)):
    token = _get_token(session_id)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/playlists",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            params={"part": "snippet,contentDetails", "mine": "true", "maxResults": 50},
        )
    return resp.json()
