"""
UniBlend Algorithm — 5-stage taste compatibility engine.

Stages:
  1. Build UserProfile (genre vector, audio vector, diversity, mood)
  2. Genre DNA similarity   — weighted Jaccard  (35%)
  3. Audio vibe similarity  — cosine similarity (35%)
  4. Social graph similarity — artist/track overlap (30%)
  5. Final score + insight generation
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Genre family mapping ───────────────────────────────────────────────────────

GENRE_FAMILIES: Dict[str, List[str]] = {
    "rock":        ["soft rock", "classic rock", "alternative rock", "indie rock",
                    "garage rock", "heartland rock", "britpop", "hard rock"],
    "soft rock":   ["rock", "classic rock", "adult contemporary"],
    "alternative": ["alternative rock", "indie rock", "britpop", "grunge", "post-punk"],
    "hip hop":     ["rap", "trap", "r&b", "urban contemporary"],
    "indie pop":   ["indie", "alternative", "indie rock"],
    "edm":         ["electronic", "dance", "house", "techno", "trance"],
    "jazz":        ["jazz", "blues", "soul", "neo soul"],
    "classical":   ["classical", "orchestral", "ambient", "new age"],
    "pop":         ["pop", "synth pop", "electropop", "dream pop"],
    "metal":       ["metal", "heavy metal", "death metal", "hard rock"],
    "folk":        ["folk", "acoustic", "singer-songwriter", "country"],
    "latin":       ["latin", "reggaeton", "salsa", "bossa nova"],
}

# Reverse map: member genre → family name
GENRE_TO_FAMILY: Dict[str, str] = {}
for _family, _members in GENRE_FAMILIES.items():
    GENRE_TO_FAMILY[_family] = _family
    for _m in _members:
        GENRE_TO_FAMILY[_m] = _family

# ── Genre-based audio defaults ─────────────────────────────────────────────────
# [energy, danceability, valence, acousticness, instrumentalness, speechiness, tempo_normalized]

GENRE_AUDIO_DEFAULTS: Dict[str, List[float]] = {
    "soft rock":  [0.55, 0.50, 0.60, 0.45, 0.05, 0.05, 0.45],
    "hip hop":    [0.70, 0.80, 0.55, 0.10, 0.05, 0.25, 0.65],
    "edm":        [0.90, 0.85, 0.65, 0.05, 0.30, 0.05, 0.80],
    "jazz":       [0.40, 0.55, 0.55, 0.70, 0.40, 0.05, 0.35],
    "classical":  [0.25, 0.25, 0.40, 0.90, 0.85, 0.02, 0.25],
    "pop":        [0.65, 0.70, 0.65, 0.25, 0.02, 0.08, 0.60],
    "metal":      [0.92, 0.45, 0.35, 0.05, 0.10, 0.05, 0.75],
    "folk":       [0.35, 0.45, 0.55, 0.80, 0.15, 0.05, 0.35],
    "indie":      [0.58, 0.58, 0.52, 0.40, 0.08, 0.05, 0.50],
    "latin":      [0.72, 0.82, 0.72, 0.20, 0.03, 0.08, 0.70],
    "r&b":        [0.60, 0.72, 0.60, 0.20, 0.04, 0.12, 0.55],
    "default":    [0.60, 0.60, 0.55, 0.30, 0.10, 0.07, 0.55],
}


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    genre_vector: Dict[str, float] = field(default_factory=dict)
    audio_vector: List[float] = field(
        default_factory=lambda: [0.60, 0.60, 0.55, 0.30, 0.10, 0.07, 0.55]
    )
    top_artists: List[str] = field(default_factory=list)
    top_tracks: List[str] = field(default_factory=list)   # "artist|||title"
    listening_diversity: float = 0.5
    dominant_mood: str = "balanced"
    has_real_audio: bool = False   # True only when real audio_features were present
    has_real_genres: bool = False  # True only when genre tags were present


@dataclass
class BlendResult:
    match_percentage: float
    match_label: str
    top_common_tracks: List[Dict]
    top_common_artists: List[Dict]
    unique_to_user1: List[Dict]
    unique_to_user2: List[Dict]
    shared_genres: List[Dict]
    genre_breakdown: Dict
    audio_profile_comparison: Dict
    vibe_summary: str
    dominant_user: str
    blend_playlist_tracks: List[Dict]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return s.lower().strip()


def _clean_artist_name(name: str) -> str:
    """Strip YouTube channel suffixes so names match Spotify artist names."""
    # Remove everything after " - Topic", " - VEVO", etc.
    name = re.sub(
        r'\s*[-–]\s*(topic|vevo|official|music|records?|entertainment|tv|hd|lyrics?|official\s+channel).*$',
        '', name, flags=re.IGNORECASE,
    )
    # Remove trailing VEVO / Official with no dash
    name = re.sub(r'\s*(vevo|official)$', '', name, flags=re.IGNORECASE)
    # Remove featured artists: "Artist ft. X", "Artist feat. X", "Artist (feat. X)"
    name = re.sub(r'\s*(ft\.?|feat\.?|featuring)\s+.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(feat\.?.*?\)', '', name, flags=re.IGNORECASE)
    return name.strip()


def _position_weight(idx: int) -> float:
    if idx < 5:
        return 3.0
    if idx < 15:
        return 2.0
    return 1.0


def _audio_default_for_genres(genres: List[str]) -> List[float]:
    for genre in genres:
        g = _norm(genre)
        if g in GENRE_AUDIO_DEFAULTS:
            return GENRE_AUDIO_DEFAULTS[g]
        family = GENRE_TO_FAMILY.get(g)
        if family and family in GENRE_AUDIO_DEFAULTS:
            return GENRE_AUDIO_DEFAULTS[family]
    return GENRE_AUDIO_DEFAULTS["default"]


def _shannon_entropy(vector: Dict[str, float]) -> float:
    values = [v for v in vector.values() if v > 0]
    if len(values) < 2:
        return 0.0
    entropy = -sum(p * math.log2(p) for p in values)
    max_entropy = math.log2(len(values))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _dominant_mood(av: List[float]) -> str:
    energy, danceability, valence = av[0], av[1], av[2]
    if energy > 0.7 and valence > 0.6:
        return "euphoric"
    if energy > 0.7 and valence < 0.4:
        return "intense"
    if energy < 0.4 and valence > 0.6:
        return "chill"
    if energy < 0.4 and valence < 0.4:
        return "melancholic"
    if danceability > 0.7:
        return "groovy"
    return "balanced"


def _weighted_jaccard(a: Dict[str, float], b: Dict[str, float]) -> float:
    all_genres = set(a.keys()) | set(b.keys())
    intersection = sum(min(a.get(g, 0), b.get(g, 0)) for g in all_genres)
    union_val = sum(max(a.get(g, 0), b.get(g, 0)) for g in all_genres)
    return intersection / union_val if union_val > 0 else 0.0


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    return dot / (mag_a * mag_b) if mag_a * mag_b > 0 else 0.0


def _match_label(score: float) -> str:
    if score >= 0.95: return "Sonic twins"
    if score >= 0.80: return "Music soulmates"
    if score >= 0.65: return "Strong harmony"
    if score >= 0.50: return "Good mix"
    if score >= 0.35: return "Interesting contrast"
    return "Opposites attract"


def _vibe_summary(u1: UserProfile, u2: UserProfile, shared: List[Dict]) -> str:
    top = [g["genre"] for g in shared[:2]]
    m1, m2 = u1.dominant_mood, u2.dominant_mood
    if top and m1 == m2:
        return f"You both share a love for {' and '.join(top)} with a {m1} vibe"
    if top:
        return f"You meet in the middle on {' and '.join(top)} — one {m1}, the other {m2}"
    if m1 == m2:
        return f"Different genres, but your listening moods are almost identical — both {m1}"
    return f"One of you is {m1}, the other is {m2} — but your audio profiles tell a deeper story"


# ── Stage 1: Build user profile ────────────────────────────────────────────────

def build_user_profile(tracks: List[Dict]) -> UserProfile:
    """
    Build a UserProfile from a list of tracks.
    Each track dict may include:
      title, artist, genres: list[str], audio_features: dict
    audio_features keys: energy, danceability, valence, acousticness,
                         instrumentalness, speechiness, tempo
    """
    if not tracks:
        return UserProfile()

    # --- Genre vector ---
    raw: Dict[str, float] = {}
    tracks_with_genres = 0
    tracks_with_audio = 0
    for idx, track in enumerate(tracks):
        if track.get("genres"):
            tracks_with_genres += 1
        if track.get("audio_features") and "energy" in (track.get("audio_features") or {}):
            tracks_with_audio += 1

    has_real_genres = tracks_with_genres >= max(1, len(tracks) * 0.1)
    has_real_audio = tracks_with_audio >= max(1, len(tracks) * 0.1)

    for idx, track in enumerate(tracks):
        w = _position_weight(idx)
        genres = track.get("genres") or []
        if not genres:
            continue
        per = w / len(genres)
        for genre in genres:
            g = _norm(genre)
            raw[g] = raw.get(g, 0) + per
            # Spread weight to related genres in the same family
            for family, members in GENRE_FAMILIES.items():
                if g == family:
                    for related in members:
                        raw[related] = raw.get(related, 0) + 0.4 * per
                elif g in members:
                    raw[family] = raw.get(family, 0) + 0.4 * per

    total = sum(raw.values())
    genre_vector = {g: w / total for g, w in raw.items()} if total > 0 else {}

    # --- Audio vector ---
    audio_sum = [0.0] * 7
    audio_count = 0
    for track in tracks:
        af = track.get("audio_features") or {}
        genres = track.get("genres") or []
        if af and "energy" in af:
            tempo = af.get("tempo", 120)
            tempo_norm = max(0.0, min(1.0, (tempo - 60) / 140))
            vec = [
                af.get("energy", 0.6),
                af.get("danceability", 0.6),
                af.get("valence", 0.55),
                af.get("acousticness", 0.3),
                af.get("instrumentalness", 0.1),
                af.get("speechiness", 0.07),
                tempo_norm,
            ]
        else:
            vec = _audio_default_for_genres(genres)
        for i, v in enumerate(vec):
            audio_sum[i] += v
        audio_count += 1

    audio_vector = (
        [v / audio_count for v in audio_sum]
        if audio_count > 0
        else GENRE_AUDIO_DEFAULTS["default"]
    )

    # --- Top artists (deduplicated, up to 50) ---
    seen: Dict[str, bool] = {}
    top_artists: List[str] = []
    for track in tracks:
        raw_artist = track.get("artist", "")
        a = _norm(_clean_artist_name(raw_artist))
        if a and a not in seen:
            seen[a] = True
            top_artists.append(a)
        if len(top_artists) >= 50:
            break

    # --- Top tracks (up to 100) ---
    top_tracks: List[str] = []
    for track in tracks[:100]:
        a = _norm(_clean_artist_name(track.get("artist", "")))
        t = _norm(track.get("title", ""))
        # Strip "(Official Video)", "[HD]" etc. from title
        t = re.sub(r'\s*[\(\[][^)\]]*?(official|video|lyrics?|hd|hq|audio|full\s+song)[^)\]]*?[\)\]]', '', t, flags=re.IGNORECASE).strip()
        if a and t:
            top_tracks.append(f"{a}|||{t}")

    diversity = _shannon_entropy(genre_vector) if genre_vector else 0.5
    mood = _dominant_mood(audio_vector)

    return UserProfile(
        genre_vector=genre_vector,
        audio_vector=audio_vector,
        top_artists=top_artists,
        top_tracks=top_tracks,
        listening_diversity=diversity,
        dominant_mood=mood,
        has_real_audio=has_real_audio,
        has_real_genres=has_real_genres,
    )


# ── Stages 2-5: Calculate blend ────────────────────────────────────────────────

def calculate_blend(
    user1_tracks: List[Dict],
    user2_tracks: List[Dict],
    user1_profile: Optional[UserProfile] = None,
    user2_profile: Optional[UserProfile] = None,
) -> Tuple[BlendResult, UserProfile, UserProfile]:
    """
    Full blend calculation.
    Pass pre-built profiles to skip Stage 1 (useful for caching).
    Returns (BlendResult, user1_profile, user2_profile).
    """
    u1 = user1_profile or build_user_profile(user1_tracks)
    u2 = user2_profile or build_user_profile(user2_tracks)

    # Stage 2 — Genre DNA
    both_have_genres = u1.has_real_genres and u2.has_real_genres

    if both_have_genres:
        genre_jaccard = _weighted_jaccard(u1.genre_vector, u2.genre_vector)
        family_bonus = 0.0
        for g1, w1 in u1.genre_vector.items():
            if w1 > 0.1:
                f1 = GENRE_TO_FAMILY.get(g1)
                for g2, w2 in u2.genre_vector.items():
                    if w2 > 0.1:
                        f2 = GENRE_TO_FAMILY.get(g2)
                        if f1 and f1 == f2 and f1 != g1 and f1 != g2:
                            family_bonus = min(family_bonus + 0.03, 0.15)
        genre_score = min(1.0, genre_jaccard + family_bonus)
    else:
        genre_score = 0.0  # excluded from weight entirely below

    # Stage 3 — Audio vibe (only meaningful when both sides have real features)
    both_have_audio = u1.has_real_audio and u2.has_real_audio
    audio_score = _cosine(u1.audio_vector, u2.audio_vector) if both_have_audio else 0.0

    # Stage 4 — Social graph (fuzzy artist matching via normalised names)
    set_a1 = set(u1.top_artists)
    set_a2 = set(u2.top_artists)
    common_artists_set = set_a1 & set_a2
    all_artists_set = set_a1 | set_a2
    # Overlap coefficient (common / min) + sqrt scaling.
    # Raw overlap of 6/50 = 12% feels wrong when 6 artists is genuinely significant.
    # sqrt(0.12) = 0.35 which better reflects the intuitive sense of shared taste.
    min_artists = min(len(set_a1), len(set_a2))
    artist_overlap_raw = len(common_artists_set) / min_artists if min_artists > 0 else 0
    artist_score = math.sqrt(artist_overlap_raw)

    set_t1 = set(u1.top_tracks)
    set_t2 = set(u2.top_tracks)
    common_tracks_set = set_t1 & set_t2
    all_tracks_set = set_t1 | set_t2
    min_tracks = min(len(set_t1), len(set_t2))
    track_overlap_raw = len(common_tracks_set) / min_tracks if min_tracks > 0 else 0
    track_score = math.sqrt(track_overlap_raw)

    social_score = 0.6 * artist_score + 0.4 * track_score

    # Stage 5 — Adaptive weights based on data availability
    # Only include a component's weight when that component has real signal
    genre_w  = 0.35 if both_have_genres else 0.0
    audio_w  = 0.35 if both_have_audio  else 0.0
    social_w = 1.0 - genre_w - audio_w   # social absorbs all unused weight

    raw = genre_w * genre_score + audio_w * audio_score + social_w * social_score
    diversity_penalty = abs(u1.listening_diversity - u2.listening_diversity) * 0.08
    mood_bonus = 0.04 if u1.dominant_mood == u2.dominant_mood else 0.0
    final_score = min(1.0, max(0.0, raw - diversity_penalty + mood_bonus))
    blend_pct = round(final_score * 100, 1)

    # --- Shared genres ---
    all_genre_keys = set(u1.genre_vector) | set(u2.genre_vector)
    shared_genres = [
        {
            "genre": g,
            "user1_weight": round(u1.genre_vector.get(g, 0), 3),
            "user2_weight": round(u2.genre_vector.get(g, 0), 3),
            "family": GENRE_TO_FAMILY.get(g, g),
        }
        for g in all_genre_keys
        if u1.genre_vector.get(g, 0) > 0 and u2.genre_vector.get(g, 0) > 0
    ]
    shared_genres.sort(
        key=lambda x: x["user1_weight"] + x["user2_weight"], reverse=True
    )

    # --- Common artists ---
    u1_a_rank = {a: i for i, a in enumerate(u1.top_artists)}
    u2_a_rank = {a: i for i, a in enumerate(u2.top_artists)}
    top_common_artists = sorted(
        [
            {
                "name": a,
                "user1_rank": u1_a_rank.get(a, 99),
                "user2_rank": u2_a_rank.get(a, 99),
                "reason": "A mutual favourite",
            }
            for a in common_artists_set
        ],
        key=lambda x: x["user1_rank"] + x["user2_rank"],
    )

    # --- Common tracks ---
    u1_t_rank = {t: i for i, t in enumerate(u1.top_tracks)}
    u2_t_rank = {t: i for i, t in enumerate(u2.top_tracks)}
    top_common_tracks = []
    for tk in common_tracks_set:
        parts = tk.split("|||", 1)
        artist_n = parts[0] if len(parts) > 1 else ""
        title_n = parts[1] if len(parts) > 1 else tk
        top_common_tracks.append(
            {
                "title": title_n,
                "artist": artist_n,
                "reason": "Both of you love this",
                "_rank": u1_t_rank.get(tk, 99) + u2_t_rank.get(tk, 99),
            }
        )
    top_common_tracks.sort(key=lambda x: x["_rank"])
    for t in top_common_tracks:
        t.pop("_rank", None)

    # --- Unique track recommendations ---
    t1_ids = set_t1
    t2_ids = set_t2
    unique_to_user1 = [
        {"title": t.get("title", ""), "artist": t.get("artist", ""), "source": "user1"}
        for t in (user1_tracks or [])
        if f"{_norm(t.get('artist',''))}|||{_norm(t.get('title',''))}" not in t2_ids
    ][:5]
    unique_to_user2 = [
        {"title": t.get("title", ""), "artist": t.get("artist", ""), "source": "user2"}
        for t in (user2_tracks or [])
        if f"{_norm(t.get('artist',''))}|||{_norm(t.get('title',''))}" not in t1_ids
    ][:5]

    # --- Audio profile comparison ---
    audio_profile_comparison = {
        "labels": ["energy", "danceability", "mood", "acoustic", "instrumental", "speech", "tempo"],
        "user1": [round(v * 100, 1) for v in u1.audio_vector],
        "user2": [round(v * 100, 1) for v in u2.audio_vector],
    }

    # --- Dominant user ---
    u1_shared_weight = sum(u1.genre_vector.get(g["genre"], 0) for g in shared_genres)
    u2_shared_weight = sum(u2.genre_vector.get(g["genre"], 0) for g in shared_genres)
    if u1_shared_weight > u2_shared_weight * 1.2:
        dominant_user = "user1"
    elif u2_shared_weight > u1_shared_weight * 1.2:
        dominant_user = "user2"
    else:
        dominant_user = "equal"

    # --- Blend playlist (40% common / 25% u1 / 25% u2 / 10% placeholder) ---
    blend_playlist: List[Dict] = []
    for t in top_common_tracks[:20]:
        blend_playlist.append({**t, "source": "both", "match_reason": "Both users love this"})
    for t in unique_to_user1[:12]:
        blend_playlist.append({**t, "match_reason": "User 1's taste — discover something new"})
    for t in unique_to_user2[:12]:
        blend_playlist.append({**t, "match_reason": "User 2's taste — discover something new"})

    result = BlendResult(
        match_percentage=blend_pct,
        match_label=_match_label(final_score),
        top_common_tracks=top_common_tracks,
        top_common_artists=top_common_artists,
        unique_to_user1=unique_to_user1,
        unique_to_user2=unique_to_user2,
        shared_genres=shared_genres,
        genre_breakdown={
            "genre_similarity": round(genre_score, 3),
            "audio_similarity": round(audio_score, 3),
            "social_similarity": round(social_score, 3),
            "final": blend_pct,
        },
        audio_profile_comparison=audio_profile_comparison,
        vibe_summary=_vibe_summary(u1, u2, shared_genres),
        dominant_user=dominant_user,
        blend_playlist_tracks=blend_playlist,
    )
    return result, u1, u2
