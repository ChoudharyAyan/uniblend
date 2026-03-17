"""
Supabase persistence layer for blend sessions.

If SUPABASE_URL / SUPABASE_SERVICE_KEY are not set, all functions
are no-ops so the app works fine without a database configured.
"""
import os
import time
from typing import Optional

_client = None


def _get_client():
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if url and key:
            from supabase import create_client
            _client = create_client(url, key)
    return _client


def persist_blend_result(session: dict) -> None:
    """
    Save a completed blend session to Supabase.
    Only called after status == "done" or "error".
    """
    db = _get_client()
    if not db:
        return
    try:
        db.table("blend_sessions").upsert({
            "blend_id": session["blend_id"],
            "spotify_display_name": session.get("spotify_display_name"),
            "ytmusic_display_name": session.get("ytmusic_display_name"),
            "status": session.get("status"),
            "result": session.get("result"),
            "error": session.get("error"),
        }).execute()
    except Exception:
        pass  # never crash the app over a DB write


def load_blend_session(blend_id: str) -> Optional[dict]:
    """
    Fetch a previously saved blend session from Supabase.
    Returns a session-shaped dict, or None if not found.
    """
    db = _get_client()
    if not db:
        return None
    try:
        resp = db.table("blend_sessions").select("*").eq("blend_id", blend_id).limit(1).execute()
        rows = resp.data
        if not rows:
            return None
        row = rows[0]
        return {
            "blend_id": row["blend_id"],
            "created_at": time.time(),  # treat as fresh for in-memory TTL
            "spotify_session": None,    # OAuth tokens are not persisted
            "ytmusic_session": None,
            "spotify_display_name": row.get("spotify_display_name"),
            "ytmusic_display_name": row.get("ytmusic_display_name"),
            "status": row.get("status", "done"),
            "result": row.get("result"),
            "error": row.get("error"),
        }
    except Exception:
        return None
