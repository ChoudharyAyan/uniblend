from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from typing import Optional
import os
import uuid

load_dotenv()

router = APIRouter()

SPOTIFY_SCOPES = (
    "user-read-private user-read-email "
    "user-top-read user-library-read "
    "playlist-read-private playlist-read-collaborative "
    "user-read-recently-played"
)

from store import spotify_tokens as _token_store, blend_sessions


def _make_oauth(state: Optional[str] = None) -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        state=state,
        cache_handler=spotipy.cache_handler.MemoryCacheHandler(),
        show_dialog=False,
    )


def _get_spotify(session_id: str) -> spotipy.Spotify:
    token_info = _token_store.get(session_id)
    if not token_info:
        raise HTTPException(status_code=401, detail="Not authenticated with Spotify")
    oauth = _make_oauth()
    if oauth.is_token_expired(token_info):
        token_info = oauth.refresh_access_token(token_info["refresh_token"])
        _token_store[session_id] = token_info
    return spotipy.Spotify(auth=token_info["access_token"])


@router.get("/auth/spotify/login")
def spotify_login(blend_id: Optional[str] = Query(None)):
    """Return the Spotify OAuth URL. Optionally associates with a blend session."""
    session_id = str(uuid.uuid4())
    state = f"{session_id}|{blend_id}" if blend_id else session_id
    oauth = _make_oauth(state=state)
    auth_url = oauth.get_authorize_url()
    return {"auth_url": auth_url, "session_id": session_id}


@router.get("/auth/spotify/callback")
def spotify_callback(code: str = Query(...), state: str = Query(...)):
    """Handle OAuth callback. Links session to blend if blend_id is in state."""
    if "|" in state:
        session_id, blend_id = state.split("|", 1)
    else:
        session_id, blend_id = state, None

    oauth = _make_oauth(state=state)
    token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
    _token_store[session_id] = token_info

    if blend_id and blend_id in blend_sessions:
        blend_sessions[blend_id]["spotify_session"] = session_id

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")[0].strip()
    if blend_id:
        return RedirectResponse(url=f"{frontend_url}/blend/{blend_id}?spotify_session={session_id}")
    return RedirectResponse(url=f"{frontend_url}?spotify_session={session_id}")


@router.get("/spotify/me")
def spotify_me(session_id: str = Query(...)):
    sp = _get_spotify(session_id)
    return sp.current_user()


@router.get("/spotify/top-tracks")
def spotify_top_tracks(session_id: str = Query(...), time_range: str = Query("medium_term")):
    sp = _get_spotify(session_id)
    return sp.current_user_top_tracks(limit=50, time_range=time_range)


@router.get("/spotify/liked-songs")
def spotify_liked_songs(session_id: str = Query(...)):
    sp = _get_spotify(session_id)
    tracks, offset = [], 0
    while len(tracks) < 200:
        batch = sp.current_user_saved_tracks(limit=50, offset=offset)
        items = batch.get("items", [])
        if not items:
            break
        tracks.extend(items)
        offset += len(items)
        if len(items) < 50:
            break
    return {"items": tracks[:200], "total": len(tracks[:200])}


@router.get("/spotify/playlists")
def spotify_playlists(session_id: str = Query(...)):
    sp = _get_spotify(session_id)
    return sp.current_user_playlists(limit=50)
