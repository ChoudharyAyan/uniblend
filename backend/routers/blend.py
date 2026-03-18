from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
import re
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import httpx
import anthropic
import os
import time
import uuid
from dotenv import load_dotenv

from store import spotify_tokens, ytmusic_tokens, blend_sessions, prune_blend_sessions
from utils.matcher import match_tracks
from blend.algorithm import calculate_blend
from db import persist_blend_result, load_blend_session

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
        # Keep artist IDs temporarily for genre enrichment; stripped before returning to client
        "_artist_ids": [a["id"] for a in t.get("artists", []) if a.get("id")],
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


def _enrich_spotify_tracks(sp: spotipy.Spotify, tracks: list) -> list:
    """
    Attach audio_features and genres to each Spotify track dict.
    Works in batches of 50 (Spotify API limit).
    """
    ids = [t["id"] for t in tracks if t.get("id")]

    # Batch fetch audio features
    features_map: dict = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        try:
            results = sp.audio_features(batch) or []
            for f in results:
                if f and f.get("id"):
                    features_map[f["id"]] = {
                        "energy": f.get("energy", 0.5),
                        "danceability": f.get("danceability", 0.5),
                        "valence": f.get("valence", 0.5),
                        "acousticness": f.get("acousticness", 0.3),
                        "instrumentalness": f.get("instrumentalness", 0.05),
                        "speechiness": f.get("speechiness", 0.05),
                        "tempo": f.get("tempo", 120),
                    }
        except Exception:
            pass

    # Collect unique artist IDs to batch-fetch genres
    artist_id_map: dict = {}  # artist_name_lower -> genres list
    # We need artist IDs from the raw track data — store them in normalised tracks
    # Re-fetch top tracks to get artist IDs (already cached in sp object)
    # Instead, collect artist names from tracks and batch-fetch by searching
    # Simpler: fetch genre info from the sp.artist() calls using artist IDs
    # The normalised tracks don't carry artist IDs, so we'll skip genre enrichment
    # for YT tracks but enrich Spotify tracks via their artist IDs.
    # We'll store artist_ids during normalisation below.

    enriched = []
    for t in tracks:
        track_id = t.get("id", "")
        af = features_map.get(track_id)
        enriched.append({
            **t,
            "audio_features": af,  # None if not available — algorithm handles this
            "genres": [],           # filled in next step
            "_artist_ids": t.get("_artist_ids", []),
        })

    # Batch fetch artist genres
    all_artist_ids = list({aid for t in enriched for aid in t.get("_artist_ids", [])})
    artist_genres_map: dict = {}
    for i in range(0, len(all_artist_ids), 50):
        batch = all_artist_ids[i:i + 50]
        try:
            results = sp.artists(batch)
            for a in (results or {}).get("artists", []):
                if a and a.get("id"):
                    artist_genres_map[a["id"]] = a.get("genres", [])
        except Exception:
            pass

    for t in enriched:
        genres = []
        for aid in t.get("_artist_ids", []):
            genres.extend(artist_genres_map.get(aid, []))
        t["genres"] = list(dict.fromkeys(genres))  # dedupe, preserve order
        t.pop("_artist_ids", None)

    return enriched


# ── YouTube Music ─────────────────────────────────────────────────────────────


def _yt_playlist_item_to_track(item: dict) -> dict:
    snippet = item.get("snippet", {})
    vid = snippet.get("resourceId", {}).get("videoId", "")
    thumbs = snippet.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
    title = snippet.get("title", "")
    # Strip channel suffixes so names match Spotify artist names
    raw_channel = snippet.get("videoOwnerChannelTitle", "")
    artist = re.sub(
        r'\s*[-–]\s*(topic|vevo|official|music|records?|entertainment|tv|hd).*$',
        '', raw_channel, flags=re.IGNORECASE,
    ).strip()
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

        # ── 3. Fallback: liked YouTube videos (for users with no YT Music data) ─
        # Only used if primary sources returned nothing.
        if not raw:
            next_page_token = None
            fetched = 0
            while fetched < 200:
                params: dict = {"part": "snippet", "myRating": "like", "maxResults": 50}
                if next_page_token:
                    params["pageToken"] = next_page_token
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )
                data = resp.json()
                if "error" in data:
                    break
                for item in data.get("items", []):
                    vid = item.get("id", "")
                    snippet = item.get("snippet", {})
                    title = snippet.get("title", "")
                    if not vid or title in ("", "Deleted video", "Private video"):
                        continue
                    thumbs = snippet.get("thumbnails", {})
                    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
                    artist = snippet.get("channelTitle", "").replace(" - Topic", "").strip()
                    raw[vid] = {
                        "id": vid,
                        "title": title,
                        "artist": artist,
                        "album": "",
                        "thumbnail": thumb,
                        "url": f"https://music.youtube.com/watch?v={vid}",
                        "source": "ytmusic",
                    }
                    fetched += 1
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

    if not raw:
        raise HTTPException(
            status_code=502,
            detail="No YouTube Music data found. Please like some songs or create a playlist on YouTube Music first.",
        )

    return list(raw.values())


# ── LLM blend score validator ─────────────────────────────────────────────────

async def _llm_validate_blend(algorithmic_score: float, blend_data: dict) -> dict:
    """
    Use Claude as a judge to sanity-check the algorithmic blend score.
    Runs on every blend — catches cases like many mutual artists but very low score.
    Returns {"validated_score": float, "reasoning": str, "adjusted": bool}
    """
    common_artists = [a["name"] for a in blend_data.get("top_common_artists", [])]
    common_tracks = [
        f"{t['artist']} - {t['title']}"
        for t in blend_data.get("top_common_tracks", [])
    ]
    shared_genres = [g["genre"] for g in blend_data.get("shared_genres", [])]
    stats = blend_data.get("stats", {})

    prompt = f"""You are a music taste compatibility judge. An algorithm computed a blend score of {algorithmic_score:.1f}% for two music listeners.

Evidence:
- Mutual favourite artists ({len(common_artists)}): {common_artists[:10] or "none"}
- Songs both love ({len(common_tracks)}): {common_tracks[:10] or "none"}
- Shared genres: {shared_genres[:8] or "none"}
- Spotify library size: {stats.get("total_spotify", 0)} tracks
- YouTube Music library size: {stats.get("total_yt", 0)} tracks
- Tracks matched across platforms: {stats.get("matched", 0)}

Does {algorithmic_score:.1f}% make intuitive sense? Consider:
- Many mutual artists or shared tracks → score should be higher (40%+)
- Zero overlap at all → score should be low (under 20%)
- The score reflects taste compatibility, not just raw overlap count

Respond with JSON only (no markdown):
{{"validated_score": <integer 0-100>, "reasoning": "<one concise sentence explaining the score>", "adjusted": <true|false>}}"""

    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    result = json.loads(text)
    result["validated_score"] = float(result["validated_score"])
    return result


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

        spotify_tracks_raw = await _fetch_spotify_tracks(sp_session)
        yt_tracks = await _fetch_yt_tracks(yt_session)

        # Enrich Spotify tracks with audio_features + artist genres
        sp = _get_spotify(sp_session)
        spotify_tracks = _enrich_spotify_tracks(sp, spotify_tracks_raw)

        # Fetch display names
        try:
            sp_user = sp.current_user()
            spotify_name = sp_user.get("display_name") or sp_user.get("id") or "Friend 1"
        except Exception:
            spotify_name = "Friend 1"

        try:
            token_info = ytmusic_tokens.get(yt_session, {})
            async with httpx.AsyncClient() as client:
                ch_resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    headers={"Authorization": f"Bearer {token_info['access_token']}"},
                    params={"part": "snippet", "mine": "true"},
                )
                ch_data = ch_resp.json()
                yt_name = (ch_data.get("items") or [{}])[0].get("snippet", {}).get("title") or "Friend 2"
        except Exception:
            yt_name = "Friend 2"

        # Strip internal _artist_ids from tracks returned to the client
        spotify_tracks_clean = [{k: v for k, v in t.items() if k != "_artist_ids"} for t in spotify_tracks]

        # Fuzzy match for the track display (matches / spotify_only / yt_only)
        matches, spotify_only, yt_only = match_tracks(spotify_tracks_clean, yt_tracks)

        # 5-stage blend algorithm
        blend_result, _u1, _u2 = calculate_blend(spotify_tracks, yt_tracks)

        # LLM sanity check — validates / corrects the algorithmic score
        llm_validated_score = blend_result.match_percentage
        llm_reasoning = blend_result.vibe_summary
        try:
            llm_result = await _llm_validate_blend(
                blend_result.match_percentage,
                {
                    "top_common_artists": blend_result.top_common_artists,
                    "top_common_tracks": blend_result.top_common_tracks,
                    "shared_genres": blend_result.shared_genres,
                    "stats": {
                        "total_spotify": len(spotify_tracks),
                        "total_yt": len(yt_tracks),
                        "matched": len(matches),
                    },
                },
            )
            llm_validated_score = llm_result["validated_score"]
            llm_reasoning = llm_result["reasoning"]
        except Exception:
            pass  # Fall back to algorithmic score silently

        session["result"] = {
            "spotify_display_name": spotify_name,
            "ytmusic_display_name": yt_name,
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
            "blend_analysis": {
                "match_percentage": llm_validated_score,
                "match_label": blend_result.match_label,
                "vibe_summary": llm_reasoning,
                "dominant_user": blend_result.dominant_user,
                "shared_genres": blend_result.shared_genres[:8],
                "genre_breakdown": blend_result.genre_breakdown,
                "top_common_artists": blend_result.top_common_artists,
                "top_common_tracks": blend_result.top_common_tracks,
                "audio_profile_comparison": blend_result.audio_profile_comparison,
                "unique_to_spotify": blend_result.unique_to_user1[:10],
                "unique_to_ytmusic": blend_result.unique_to_user2[:10],
                "blend_playlist_tracks": blend_result.blend_playlist_tracks[:20],
            },
        }
        session["status"] = "done"
        persist_blend_result(session)   # save to Supabase (no-op if not configured)
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        persist_blend_result(session)


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
        "spotify_display_name": None,
        "ytmusic_display_name": None,
    }
    return {"blend_id": blend_id}


@router.get("/blend/session/{blend_id}")
async def get_blend_session(blend_id: str, background_tasks: BackgroundTasks):
    """Poll blend session status. Triggers computation when both platforms connected."""
    session = blend_sessions.get(blend_id)

    # Not in memory — try loading from Supabase (handles Railway restarts)
    if not session:
        session = load_blend_session(blend_id)
        if session:
            blend_sessions[blend_id] = session  # restore to memory cache
        else:
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
        "spotify_display_name": session.get("spotify_display_name"),
        "ytmusic_display_name": session.get("ytmusic_display_name"),
        "result": session["result"],
        "error": session["error"],
    }
