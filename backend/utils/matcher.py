import re
from fuzzywuzzy import fuzz
from typing import List, Dict, Tuple


def normalize(text: str) -> str:
    """Lowercase, strip parenthetical notes and punctuation."""
    text = text.lower()
    # Remove content in parens/brackets: (feat. X), [Official Video], etc.
    text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
    # Remove featuring credits outside parens
    text = re.sub(r'\bft\.?\s.*', '', text)
    text = re.sub(r'\bfeat\.?\s.*', '', text)
    # Keep only alphanumeric + spaces
    text = re.sub(r'[^a-z0-9 ]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_yt_title(title: str) -> Tuple[str, str]:
    """
    Try to parse 'Artist - Song Title' from a YouTube video title.
    Returns (artist, title). Falls back to ('', raw_title).
    """
    if ' - ' in title:
        parts = title.split(' - ', 1)
        return parts[0].strip(), parts[1].strip()
    return '', title.strip()


def score_pair(sp_title: str, sp_artist: str, yt_title: str, yt_artist: str) -> float:
    """Combined fuzzy score for a Spotify <-> YouTube track pair (0-100)."""
    t_score = fuzz.token_sort_ratio(normalize(sp_title), normalize(yt_title))
    if sp_artist and yt_artist:
        a_score = fuzz.token_sort_ratio(normalize(sp_artist), normalize(yt_artist))
    else:
        a_score = 50  # neutral when artist unknown
    return t_score * 0.65 + a_score * 0.35


def match_tracks(
    spotify_tracks: List[Dict],
    yt_tracks: List[Dict],
    threshold: float = 72,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Greedy best-match between two normalised track lists.

    Each item in spotify_tracks / yt_tracks must have keys:
        title, artist, thumbnail, url (optional)

    Returns: (matches, spotify_only, yt_only)
    Each match: {spotify, ytmusic, score}
    """
    matched_yt: set = set()
    matches: List[Dict] = []
    matched_sp: set = set()

    for si, sp in enumerate(spotify_tracks):
        best_score = 0.0
        best_yi = -1
        for yi, yt in enumerate(yt_tracks):
            if yi in matched_yt:
                continue
            s = score_pair(sp['title'], sp['artist'], yt['title'], yt['artist'])
            if s > best_score:
                best_score = s
                best_yi = yi

        if best_score >= threshold and best_yi >= 0:
            matches.append({
                'spotify': sp,
                'ytmusic': yt_tracks[best_yi],
                'score': round(best_score, 1),
            })
            matched_yt.add(best_yi)
            matched_sp.add(si)

    spotify_only = [sp for i, sp in enumerate(spotify_tracks) if i not in matched_sp]
    yt_only = [yt for i, yt in enumerate(yt_tracks) if i not in matched_yt]

    # Sort matches by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches, spotify_only, yt_only
