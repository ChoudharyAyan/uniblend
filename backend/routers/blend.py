from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import httpx
import os
import time
import uuid
from dotenv import load_dotenv

from store import spotify_tokens, ytmusic_tokens, blend_sessions, prune_blend_sessions
from utils.matcher import match_tracks

load_dotenv()

router = APIRouter()

SPOTIFY_SCOPES = (
    "user-read-private user-read-email "
    "user-top-read user-library-read "
    "playlist-read-private playlist-read-collaborative "
    "user-read-recently-played"
)


# ── Spotify ──────────────────────────────────────────────────────────────────

def _get_spotify(session_id: str) -> spotipy.Spotify:
    token_info = spotify_tokens.get(session_id)
    if not token_info:
        raise HTTPException(status_code=401, detail="Spotify session not found")
    oauth = SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        cache_handler=spotipy.cache_handler.MemoryCacheHandler(),
    )
    if oauth.is_token_expired(token_info):
        token_info = oauth.refresh_access_token(token_info["refresh_token"])
        spotify_tokens[session_id] = token_info
    return spotipy.Spotify(auth=token_info["access_token"])


def _normalise_spotify_track(t: dict) -> dict:
    images = t.get("album", {}).get("images", [])
    return {
        "id": t.get("id", ""),
        "title": t.get("name", ""),
        "artist": ", ".join(a["name"] for a in t.get("artists", [])),
        "album": t.get("album", {}).get("name", ""),
        "thumbnail": images[0]["url"] if images else "",
        "url": t.get("external_urls", {}).get("spotify", ""),
        "source": "spotify",
    }


async def _fetch_spotify_tracks(session_id: str) -> list:
    """
    Build a taste profile from:
    - Top tracks across short / medium / long term  (what you actually listen to)
    - Recently played                               (recent listening behaviour)
    No liked songs — likes ≠ listening habits.
    """
    sp = _get_spotify(session_id)
    raw: dict = {}  # id -> track, de-duplicate

    # Top tracks — three time ranges
    for time_range in ("short_term", "medium_term", "long_term"):
        result = sp.current_user_top_tracks(limit=50, time_range=time_range)
        for t in result.get("items", []):
            if t and t.get("id"):
                raw[t["id"]] = t

    # Recently played (last 50 plays)
    try:
        recent = sp.current_user_recently_played(limit=50)
        for item in recent.get("items", []):
            t = item.get("track")
            if t and t.get("id") and t["id"] not in raw:
                raw[t["id"]] = t
    except Exception:
        pass  # scope may not cover this on existing tokens

    return [_normalise_spotify_track(t) for t in raw.values()]


# ── YouTube Music ─────────────────────────────────────────────────────────────


def _yt_playlist_item_to_track(item: dict) -> dict:
    snippet = item.get("snippet", {})
    vid = snippet.get("resourceId", {}).get("videoId", "")
    thumbs = snippet.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
    title = snippet.get("title", "")
    # Strip common suffixes like "(Official Video)", "[HQ]" etc.
    artist = snippet.get("videoOwnerChannelTitle", "").replace(" - Topic", "").strip()
    return {
        "id": vid,
        "title": title,
        "artist": artist,
        "album": "",
        "thumbnail": thumb,
        "url": f"https://music.youtube.com/watch?v={vid}",
        "source": "ytmusic",
    }


async def _fetch_playlist_tracks(client: httpx.AsyncClient, playlist_id: str, token: str) -> list:
    """Fetch all items from a YouTube playlist via Data API."""
    tracks = []
    next_page = None
    while len(tracks) < 500:
        params = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
        if next_page:
            params["pageToken"] = next_page
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        data = resp.json()
        if "error" in data:
            break
        for item in data.get("items", []):
            t = _yt_playlist_item_to_track(item)
            if t["id"] and t["title"] not in ("", "Deleted video", "Private video"):
                tracks.append(t)
        next_page = data.get("nextPageToken")
        if not next_page or not data.get("items"):
            break
    return tracks


async def _fetch_yt_tracks(session_id: str) -> list:
    """
    Build a YouTube Music taste profile using the YouTube Data API:
    1. LM playlist  — YouTube Music liked songs (auto-playlist)
    2. User playlists — all their created/saved playlists and their tracks
    3. ytmusicapi   — history + liked songs (best effort; logs error if it fails)
    """
    token_info = ytmusic_tokens.get(session_id)
    if not token_info:
        raise HTTPException(status_code=401, detail="YouTube Music session not found")

    access_token = token_info["access_token"]
    raw: dict = {}  # videoId -> track dict

    async with httpx.AsyncClient() as client:
        # ── 1. LM playlist (YouTube Music Liked Songs) ────────────────────────
        for t in await _fetch_playlist_tracks(client, "LM", access_token):
            raw[t["id"]] = t

        # ── 2. User's own playlists ───────────────────────────────────────────
        pl_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/playlists",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"part": "snippet,contentDetails", "mine": "true", "maxResults": 50},
        )
        pl_data = pl_resp.json()
        for pl in pl_data.get("items", []):
            pl_id = pl.get("id", "")
            if not pl_id:
                continue
            for t in await _fetch_playlist_tracks(client, pl_id, access_token):
                if t["id"] not in raw:
                    raw[t["id"]] = t

        # Liked YouTube videos skipped — videoCategoryId filter is unreliable
        # and pulls non-music content. LM playlist + user playlists are sufficient.

    # ytmusicapi (history/liked) requires TV_EMBEDDED OAuth client type,
    # incompatible with standard web app credentials — skipped for now.

    if not raw:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve any YouTube Music tracks. Make sure you have liked songs or playlists.",
        )

    return list(raw.values())


# ── Blend endpoint ────────────────────────────────────────────────────────────

@router.get("/blend/preview")
async def blend_preview(
    spotify_session: str = Query(...),
    ytmusic_session: str = Query(...),
    threshold: float = Query(72),
):
    """
    Fetch taste profiles from both platforms, fuzzy-match them, and return:
    - matches      — tracks found on both (sorted by score desc)
    - spotify_only — tracks only on Spotify
    - yt_only      — tracks only on YouTube Music
    - stats        — counts
    """
    spotify_tracks = await _fetch_spotify_tracks(spotify_session)
    yt_tracks = await _fetch_yt_tracks(ytmusic_session)

    matches, spotify_only, yt_only = match_tracks(
        spotify_tracks, yt_tracks, threshold=threshold
    )

    return {
        "matches": matches,
        "spotify_only": spotify_only[:50],
        "yt_only": yt_only[:50],
        "stats": {
            "total_spotify": len(spotify_tracks),
            "total_yt": len(yt_tracks),
            "matched": len(matches),
            "spotify_only": len(spotify_only),
            "yt_only": len(yt_only),
        },
    }


# ── Blend session endpoints ───────────────────────────────────────────────────

async def _compute_blend(blend_id: str) -> None:
    """Background task: compute blend and cache result in blend_sessions."""
    session = blend_sessions.get(blend_id)
    if not session:
        return
    try:
        sp_session = session["spotify_session"]
        yt_session = session["ytmusic_session"]
        spotify_tracks = await _fetch_spotify_tracks(sp_session)
        yt_tracks = await _fetch_yt_tracks(yt_session)
        matches, spotify_only, yt_only = match_tracks(spotify_tracks, yt_tracks)
        session["result"] = {
            "matches": matches,
            "spotify_only": spotify_only[:50],
            "yt_only": yt_only[:50],
            "stats": {
                "total_spotify": len(spotify_tracks),
                "total_yt": len(yt_tracks),
                "matched": len(matches),
                "spotify_only": len(spotify_only),
                "yt_only": len(yt_only),
            },
        }
        session["status"] = "done"
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)


@router.post("/blend/session")
def create_blend_session():
    """Create a new shareable blend session. Returns blend_id."""
    prune_blend_sessions()
    blend_id = str(uuid.uuid4())[:8]
    blend_sessions[blend_id] = {
        "blend_id": blend_id,
        "created_at": time.time(),
        "spotify_session": None,
        "ytmusic_session": None,
        "status": "waiting",
        "result": None,
        "error": None,
    }
    return {"blend_id": blend_id}


@router.get("/blend/session/{blend_id}")
async def get_blend_session(blend_id: str, background_tasks: BackgroundTasks):
    """Poll blend session status. Triggers computation when both platforms connected."""
    session = blend_sessions.get(blend_id)
    if not session:
        raise HTTPException(status_code=404, detail="Blend session not found")

    # Trigger background computation once both sessions are present
    if (
        session["status"] == "waiting"
        and session["spotify_session"]
        and session["ytmusic_session"]
    ):
        session["status"] = "computing"
        background_tasks.add_task(_compute_blend, blend_id)

    return {
        "blend_id": blend_id,
        "status": session["status"],
        "spotify_connected": session["spotify_session"] is not None,
        "ytmusic_connected": session["ytmusic_session"] is not None,
        "result": session["result"],
        "error": session["error"],
    }
