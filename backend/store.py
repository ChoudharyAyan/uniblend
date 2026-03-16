import time

# Shared in-memory token stores
spotify_tokens: dict = {}   # session_id -> spotipy token_info
ytmusic_tokens: dict = {}   # session_id -> google token_info

# Blend sessions: blend_id -> session dict
blend_sessions: dict = {}
# Each entry:
# {
#   "blend_id": str,
#   "created_at": float,
#   "spotify_session": str | None,   # key into spotify_tokens
#   "ytmusic_session": str | None,   # key into ytmusic_tokens
#   "status": "waiting" | "computing" | "done" | "error",
#   "result": dict | None,
#   "error": str | None,
# }


def prune_blend_sessions(max_age_seconds: int = 86400) -> None:
    """Remove blend sessions older than max_age_seconds (default 24h)."""
    cutoff = time.time() - max_age_seconds
    stale = [k for k, v in blend_sessions.items() if v["created_at"] < cutoff]
    for k in stale:
        blend_sessions.pop(k, None)
