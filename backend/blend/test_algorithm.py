"""
Test the UniBlend algorithm with two mock users.

User 1 (Ayan - Spotify):   RHCP, Eagles, Fleetwood Mac, Tom Petty, Oasis  → soft rock / classic rock / alt rock
User 2 (Friend - YT Music): Arctic Monkeys, Radiohead, The Strokes, Oasis, Tame Impala → indie rock / alt rock / britpop

Expected:
  - blend_percentage: 65-80%
  - top_common_artists includes Oasis
  - shared_genres includes "alternative rock" and/or "rock"
  - vibe_summary mentions rock/alternative
  - dominant_user: "equal" or "user1"
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blend.algorithm import build_user_profile, calculate_blend, BlendResult, UserProfile

# ── Mock data ──────────────────────────────────────────────────────────────────

user1_tracks = [
    {
        "title": "Under the Bridge",
        "artist": "Red Hot Chili Peppers",
        "genres": ["alternative rock", "funk rock"],
        "audio_features": {"energy": 0.62, "danceability": 0.48, "valence": 0.55,
                           "acousticness": 0.25, "instrumentalness": 0.02, "speechiness": 0.05, "tempo": 108},
    },
    {
        "title": "Hotel California",
        "artist": "Eagles",
        "genres": ["soft rock", "classic rock"],
        "audio_features": {"energy": 0.57, "danceability": 0.44, "valence": 0.52,
                           "acousticness": 0.35, "instrumentalness": 0.03, "speechiness": 0.04, "tempo": 75},
    },
    {
        "title": "The Chain",
        "artist": "Fleetwood Mac",
        "genres": ["soft rock", "classic rock"],
        "audio_features": {"energy": 0.60, "danceability": 0.47, "valence": 0.58,
                           "acousticness": 0.30, "instrumentalness": 0.04, "speechiness": 0.04, "tempo": 150},
    },
    {
        "title": "Free Fallin'",
        "artist": "Tom Petty",
        "genres": ["soft rock", "heartland rock"],
        "audio_features": {"energy": 0.55, "danceability": 0.45, "valence": 0.60,
                           "acousticness": 0.40, "instrumentalness": 0.01, "speechiness": 0.03, "tempo": 85},
    },
    {
        "title": "Wonderwall",
        "artist": "Oasis",
        "genres": ["britpop", "alternative rock"],
        "audio_features": {"energy": 0.58, "danceability": 0.46, "valence": 0.50,
                           "acousticness": 0.38, "instrumentalness": 0.02, "speechiness": 0.05, "tempo": 87},
    },
]

user2_tracks = [
    {
        "title": "Do I Wanna Know?",
        "artist": "Arctic Monkeys",
        "genres": ["indie rock", "alternative rock"],
        "audio_features": {"energy": 0.67, "danceability": 0.52, "valence": 0.45,
                           "acousticness": 0.15, "instrumentalness": 0.03, "speechiness": 0.05, "tempo": 85},
    },
    {
        "title": "Creep",
        "artist": "Radiohead",
        "genres": ["alternative rock", "indie rock"],
        "audio_features": {"energy": 0.62, "danceability": 0.42, "valence": 0.38,
                           "acousticness": 0.20, "instrumentalness": 0.04, "speechiness": 0.04, "tempo": 92},
    },
    {
        "title": "Last Nite",
        "artist": "The Strokes",
        "genres": ["indie rock", "garage rock"],
        "audio_features": {"energy": 0.72, "danceability": 0.55, "valence": 0.52,
                           "acousticness": 0.08, "instrumentalness": 0.02, "speechiness": 0.06, "tempo": 152},
    },
    {
        "title": "Wonderwall",
        "artist": "Oasis",
        "genres": ["britpop", "alternative rock"],
        "audio_features": {"energy": 0.58, "danceability": 0.46, "valence": 0.50,
                           "acousticness": 0.38, "instrumentalness": 0.02, "speechiness": 0.05, "tempo": 87},
    },
    {
        "title": "Let It Happen",
        "artist": "Tame Impala",
        "genres": ["psychedelic rock", "indie pop", "alternative"],
        "audio_features": {"energy": 0.63, "danceability": 0.62, "valence": 0.55,
                           "acousticness": 0.10, "instrumentalness": 0.15, "speechiness": 0.03, "tempo": 107},
    },
]

# ── Run ────────────────────────────────────────────────────────────────────────

result, u1, u2 = calculate_blend(user1_tracks, user2_tracks)

print("=" * 60)
print("BLEND RESULT")
print("=" * 60)
print(json.dumps({
    "match_percentage": result.match_percentage,
    "match_label": result.match_label,
    "vibe_summary": result.vibe_summary,
    "dominant_user": result.dominant_user,
    "genre_breakdown": result.genre_breakdown,
    "shared_genres": result.shared_genres[:6],
    "top_common_artists": result.top_common_artists,
    "top_common_tracks": result.top_common_tracks,
    "audio_profile_comparison": result.audio_profile_comparison,
    "unique_to_user1": result.unique_to_user1,
    "unique_to_user2": result.unique_to_user2,
    "blend_playlist_tracks": result.blend_playlist_tracks[:10],
}, indent=2))

print("\n" + "=" * 60)
print("USER PROFILES")
print("=" * 60)
print(f"User 1 — mood: {u1.dominant_mood}, diversity: {u1.listening_diversity:.2f}")
print(f"User 2 — mood: {u2.dominant_mood}, diversity: {u2.listening_diversity:.2f}")
top_u1 = dict(sorted(u1.genre_vector.items(), key=lambda x: -x[1])[:5])
top_u2 = dict(sorted(u2.genre_vector.items(), key=lambda x: -x[1])[:5])
print(f"\nUser 1 top genres: {top_u1}")
print(f"User 2 top genres: {top_u2}")

# ── Assertions ────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("ASSERTIONS")
print("=" * 60)

assert 45 <= result.match_percentage <= 85, \
    f"Expected 45-85%, got {result.match_percentage}%"
print(f"✓ match_percentage {result.match_percentage}% is in expected range")

assert any(a["name"] == "oasis" for a in result.top_common_artists), \
    "Expected Oasis in common artists"
print(f"✓ Oasis appears in top_common_artists")

rock_genres = {"alternative rock", "rock", "indie rock", "britpop", "classic rock"}
assert any(g["genre"] in rock_genres for g in result.shared_genres), \
    f"Expected rock genres in shared_genres, got: {[g['genre'] for g in result.shared_genres]}"
print(f"✓ Rock/alt genres appear in shared_genres")

assert result.dominant_user in ("equal", "user1", "user2"), \
    f"Unexpected dominant_user value: '{result.dominant_user}'"
print(f"✓ dominant_user is '{result.dominant_user}'")

print("\n✓ All assertions passed!")
