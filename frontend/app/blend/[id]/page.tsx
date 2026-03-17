"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Platform = "spotify" | "ytmusic";
type BlendStatus = "waiting" | "computing" | "done" | "error";
type Tab = "matches" | "spotify_only" | "yt_only";

interface Track {
  id: string;
  title: string;
  artist: string;
  thumbnail: string;
  url: string;
  source: string;
  raw_title?: string;
}

interface Match {
  spotify: Track;
  ytmusic: Track;
  score: number;
}

interface BlendAnalysis {
  match_percentage: number;
  match_label: string;
  vibe_summary: string;
  dominant_user: "user1" | "user2" | "equal";
  shared_genres: { genre: string; weight: number }[];
  top_common_artists: { name: string; count: number }[];
  top_common_tracks: { artist: string; title: string }[];
  unique_to_spotify: string[];
  unique_to_ytmusic: string[];
}

interface BlendResult {
  matches: Match[];
  spotify_only: Track[];
  yt_only: Track[];
  stats: {
    total_spotify: number;
    total_yt: number;
    matched: number;
    spotify_only: number;
    yt_only: number;
  };
  blend_analysis?: BlendAnalysis;
}

interface SessionStatus {
  blend_id: string;
  status: BlendStatus;
  spotify_connected: boolean;
  ytmusic_connected: boolean;
  result: BlendResult | null;
  error: string | null;
}

// ── Brand logos ───────────────────────────────────────────────────────────────

function SpotifyLogo({ size = 56 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 496 512" aria-label="Spotify">
      <path fill="#1ED760" d="M248 8C111.1 8 0 119.1 0 256s111.1 248 248 248 248-111.1 248-248S384.9 8 248 8zm100.7 364.9c-4.2 0-6.8-1.3-10.7-3.6-62.4-37.6-135-39.2-206.7-24.5-3.9 1-9 2.6-11.9 2.6-9.7 0-15.8-7.7-15.8-15.8 0-10.3 6.1-15.2 13.6-16.8 81.9-18.1 165.6-16.5 237 26.2 6.1 3.9 9.7 7.4 9.7 16.5s-7.1 15.4-15.2 15.4zm26.9-65.6c-5.2 0-8.7-2.3-12.3-4.2-62.5-37-155.7-51.9-238.6-29.4-4.8 1.3-7.4 2.6-11.9 2.6-10.7 0-19.4-8.7-19.4-19.4s5.2-17.8 15.5-20.7c27.8-7.8 56.2-13.6 97.8-13.6 64.9 0 127.6 16.1 177 45.5 8.1 4.5 11.3 11 11.3 19.4 0 10.7-8.7 19.8-19.4 19.8zm31-76.2c-5.2 0-8.4-1.3-12.9-3.9-71.2-42.5-198.5-52.7-280.9-29.7-3.9 1-8.1 2.6-12.9 2.6-13.2 0-23.3-10.3-23.3-23.6 0-13.6 8.4-21.3 17.4-23.9 35.2-10.3 74.6-15.2 117.5-15.2 73 0 149.5 15.2 205.4 47.8 7.8 4.5 12.9 10.7 12.9 22.6 0 13.2-10.3 23.3-23.2 23.3z"/>
    </svg>
  );
}

function YTMusicLogo({ size = 56 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-label="YouTube Music">
      <circle cx="24" cy="24" r="24" fill="#FF0000" />
      <circle cx="24" cy="24" r="12" fill="white" />
      <polygon points="21,18 31,24 21,30" fill="#FF0000" />
    </svg>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function BlendRoomPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [serverStatus, setServerStatus] = useState<SessionStatus | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [myPlatform, setMyPlatform] = useState<Platform | null>(null);
  const [connecting, setConnecting] = useState<Platform | null>(null);
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState<Tab>("matches");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!id) return;
    const spotifySession = searchParams.get("spotify_session");
    const ytSession = searchParams.get("ytmusic_session");
    if (spotifySession) {
      localStorage.setItem(`blend_${id}_platform`, "spotify");
      localStorage.setItem(`blend_${id}_session_id`, spotifySession);
      setMyPlatform("spotify");
      window.history.replaceState({}, "", `/blend/${id}`);
    } else if (ytSession) {
      localStorage.setItem(`blend_${id}_platform`, "ytmusic");
      localStorage.setItem(`blend_${id}_session_id`, ytSession);
      setMyPlatform("ytmusic");
      window.history.replaceState({}, "", `/blend/${id}`);
    } else {
      const saved = localStorage.getItem(`blend_${id}_platform`) as Platform | null;
      if (saved) setMyPlatform(saved);
    }
  }, [id, searchParams]);

  useEffect(() => {
    if (!id) return;
    const poll = async () => {
      try {
        const { data } = await api.get<SessionStatus>(`/blend/session/${id}`);
        setServerStatus(data);
        if (data.status === "done" || data.status === "error") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch (err: any) {
        if (err?.response?.status === 404) {
          setNotFound(true);
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      }
    };
    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [id]);

  const handleConnect = async (platform: Platform) => {
    setConnecting(platform);
    try {
      const endpoint =
        platform === "spotify"
          ? `/auth/spotify/login?blend_id=${id}`
          : `/auth/ytmusic/login?blend_id=${id}`;
      const { data } = await api.get<{ auth_url: string }>(endpoint);
      window.location.href = data.auth_url;
    } catch {
      alert("Failed to start login. Is the backend running?");
      setConnecting(null);
    }
  };

  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Not found ──────────────────────────────────────────────────────────────
  if (notFound) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center text-white">
        <div className="text-center px-6">
          <p className="text-red-400 mb-6">This blend doesn't exist or has expired.</p>
          <button onClick={() => router.push("/")} className="px-6 py-2.5 rounded-full bg-white/10 hover:bg-white/15 transition text-sm font-medium">
            Create a new blend
          </button>
        </div>
      </div>
    );
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (!serverStatus) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const { spotify_connected, ytmusic_connected, status, result, error } = serverStatus;
  const shareUrl = typeof window !== "undefined" ? window.location.href : "";

  // ── Done ───────────────────────────────────────────────────────────────────
  if (status === "done" && result) {
    const { stats, matches, spotify_only, yt_only, blend_analysis } = result;
    const tabs: { key: Tab; label: string; count: number; color: string }[] = [
      { key: "matches", label: "In Common", count: stats.matched, color: "violet" },
      { key: "spotify_only", label: "Spotify only", count: stats.spotify_only, color: "green" },
      { key: "yt_only", label: "YouTube only", count: stats.yt_only, color: "red" },
    ];

    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white">
        <div className="max-w-3xl mx-auto px-6 py-12">
          <button onClick={() => router.push("/")} className="text-xs text-gray-600 hover:text-gray-400 mb-10 inline-flex items-center gap-1.5 transition">
            ← New blend
          </button>

          {/* Header */}
          <div className="mb-10">
            <div className="flex items-center gap-3 mb-3">
              <SpotifyLogo size={32} />
              <div className="flex-1 h-px bg-gradient-to-r from-green-500/30 via-violet-500/40 to-red-500/30" />
              <YTMusicLogo size={32} />
            </div>
            <h1 className="text-3xl font-bold mt-4">Your Blend</h1>
            <p className="text-gray-500 text-sm mt-1">
              {stats.total_spotify} Spotify tracks · {stats.total_yt} YouTube Music tracks
            </p>
          </div>

          {/* Blend Score (algorithm result) */}
          {blend_analysis && (
            <div className="mb-8 rounded-2xl bg-[#111] border border-white/5 p-6">
              <div className="flex items-center gap-6 mb-4">
                <div className="text-center shrink-0">
                  <div className="text-5xl font-bold text-violet-300 tabular-nums">
                    {Math.round(blend_analysis.match_percentage)}%
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{blend_analysis.match_label}</div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-300 leading-relaxed">{blend_analysis.vibe_summary}</p>
                  {blend_analysis.dominant_user !== "equal" && (
                    <p className="text-xs text-gray-600 mt-2">
                      Leaning more{" "}
                      <span className={blend_analysis.dominant_user === "user1" ? "text-green-400" : "text-red-400"}>
                        {blend_analysis.dominant_user === "user1" ? "Spotify" : "YouTube Music"}
                      </span>
                    </p>
                  )}
                </div>
              </div>

              {/* Shared genres */}
              {blend_analysis.shared_genres.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-gray-600 mb-2">Shared genres</p>
                  <div className="flex flex-wrap gap-2">
                    {blend_analysis.shared_genres.map((g, i) => (
                      <span key={i} className="text-xs px-3 py-1 rounded-full bg-violet-900/30 border border-violet-800/40 text-violet-300 capitalize">
                        {g.genre}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Top common artists */}
              {blend_analysis.top_common_artists.length > 0 && (
                <div>
                  <p className="text-xs text-gray-600 mb-2">Mutual favourites</p>
                  <div className="flex flex-wrap gap-2">
                    {blend_analysis.top_common_artists.map((a, i) => (
                      <span key={i} className="text-xs px-3 py-1 rounded-full bg-white/5 border border-white/10 text-gray-300 capitalize">
                        {a.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 mb-8">
            <div className="rounded-2xl bg-violet-950/40 border border-violet-900/50 p-5 text-center">
              <div className="text-3xl font-bold text-violet-300 mb-1">{stats.matched}</div>
              <div className="text-xs text-gray-500">In common</div>
            </div>
            <div className="rounded-2xl bg-[#111] border border-white/5 p-5 text-center">
              <div className="text-3xl font-bold text-green-400 mb-1">{stats.spotify_only}</div>
              <div className="text-xs text-gray-500">Spotify only</div>
            </div>
            <div className="rounded-2xl bg-[#111] border border-white/5 p-5 text-center">
              <div className="text-3xl font-bold text-red-400 mb-1">{stats.yt_only}</div>
              <div className="text-xs text-gray-500">YouTube only</div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mb-6 p-1 bg-white/5 rounded-xl w-fit">
            {tabs.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  tab === t.key
                    ? "bg-white/10 text-white shadow-sm"
                    : "text-gray-500 hover:text-gray-300"
                }`}>
                {t.label}
                <span className="ml-2 text-xs opacity-60">{t.count}</span>
              </button>
            ))}
          </div>

          {/* Track list */}
          <div className="space-y-1.5">
            {tab === "matches" && matches.map((m, i) => <MatchCard key={i} match={m} />)}
            {tab === "spotify_only" && spotify_only.map((t, i) => <TrackCard key={i} track={t} />)}
            {tab === "yt_only" && yt_only.map((t, i) => <TrackCard key={i} track={t} />)}
            {tab === "matches" && matches.length === 0 && (
              <div className="text-center py-16 text-gray-600">
                <p className="text-4xl mb-4">🎵</p>
                <p>No matches found — very different tastes!</p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (status === "error") {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center text-white">
        <div className="text-center px-6">
          <p className="text-red-400 mb-6">{error ?? "Something went wrong computing the blend."}</p>
          <button onClick={() => router.push("/")} className="px-6 py-2.5 rounded-full bg-white/10 hover:bg-white/15 transition text-sm font-medium">
            Try again
          </button>
        </div>
      </div>
    );
  }

  // ── Computing ──────────────────────────────────────────────────────────────
  if (status === "computing") {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center text-white">
        <div className="text-center">
          <div className="flex items-center justify-center gap-3 mb-8">
            <SpotifyLogo size={40} />
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div key={i} className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
            <YTMusicLogo size={40} />
          </div>
          <p className="text-lg font-semibold text-white mb-1">Blending your taste…</p>
          <p className="text-gray-600 text-sm">This takes about 10–20 seconds</p>
        </div>
      </div>
    );
  }

  // ── Waiting ────────────────────────────────────────────────────────────────
  const availablePlatform: Platform | null =
    !spotify_connected ? "spotify" : !ytmusic_connected ? "ytmusic" : null;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="max-w-2xl mx-auto px-6 py-14">
        <button onClick={() => router.push("/")} className="text-xs text-gray-600 hover:text-gray-400 mb-10 inline-flex items-center gap-1.5 transition">
          ← Home
        </button>

        <h1 className="text-3xl font-bold mb-1">Blend Room</h1>
        <p className="text-gray-500 text-sm mb-10">
          Both friends connect their platform to start the blend.
        </p>

        {/* Share link */}
        <div className="bg-[#111] border border-white/5 rounded-2xl p-4 flex items-center gap-3 mb-10">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-gray-600 mb-0.5">Share this link with your friend</p>
            <p className="text-gray-400 text-sm truncate">{shareUrl}</p>
          </div>
          <button onClick={copyLink}
            className={`shrink-0 text-xs px-4 py-2 rounded-lg font-medium transition-all ${
              copied
                ? "bg-green-600/20 text-green-400 border border-green-600/30"
                : "bg-violet-600 hover:bg-violet-500 text-white"
            }`}>
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>

        {/* Platform cards */}
        <div className="grid grid-cols-2 gap-4 mb-10">
          {(["spotify", "ytmusic"] as Platform[]).map((p) => {
            const isConnected = p === "spotify" ? spotify_connected : ytmusic_connected;
            const isMine = myPlatform === p;
            const isSpotify = p === "spotify";

            return (
              <div key={p} className={`rounded-2xl border p-6 flex flex-col items-center gap-4 transition-all ${
                isConnected
                  ? isSpotify
                    ? "border-green-800/50 bg-green-950/20"
                    : "border-red-800/50 bg-red-950/20"
                  : "border-white/5 bg-[#111]"
              }`}>
                {isSpotify ? <SpotifyLogo size={52} /> : <YTMusicLogo size={52} />}

                <p className="font-semibold text-sm">{isSpotify ? "Spotify" : "YouTube Music"}</p>

                <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                  isConnected
                    ? isSpotify
                      ? "bg-green-900/40 text-green-400"
                      : "bg-red-900/40 text-red-400"
                    : "bg-white/5 text-gray-600"
                }`}>
                  {isConnected ? "● Connected" : "○ Not connected"}
                </span>

                {!isConnected && (
                  <button
                    onClick={() => handleConnect(p)}
                    disabled={connecting === p}
                    className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-all disabled:opacity-60 ${
                      isSpotify
                        ? "bg-[#1ED760] hover:bg-[#1db954] text-black"
                        : "bg-[#FF0000] hover:bg-red-600 text-white"
                    }`}>
                    {connecting === p ? "Redirecting…" : `Connect ${isSpotify ? "Spotify" : "YouTube Music"}`}
                  </button>
                )}

                {isConnected && (
                  <p className="text-xs text-gray-600">
                    {isMine ? "You connected this" : "Friend connected"}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Waiting indicator */}
        {(spotify_connected || ytmusic_connected) && availablePlatform && (
          <div className="text-center text-gray-600 text-sm flex items-center justify-center gap-2">
            <div className="w-3.5 h-3.5 border border-gray-600 border-t-transparent rounded-full animate-spin" />
            Waiting for {availablePlatform === "spotify" ? "Spotify" : "YouTube Music"} to connect…
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MatchCard({ match }: { match: Match }) {
  const { spotify, ytmusic, score } = match;
  return (
    <div className="rounded-xl bg-[#111] border border-white/5 p-4 flex items-center gap-4 hover:bg-white/5 transition cursor-pointer" onClick={() => window.open(spotify.url, "_blank")}>
      <div className="w-11 h-11 shrink-0">
        {spotify.thumbnail && (
          <img src={spotify.thumbnail} alt="" className="w-11 h-11 rounded-lg object-cover" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{spotify.title}</p>
        <p className="text-xs text-gray-500 truncate mt-0.5">{spotify.artist}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <a href={spotify.url} target="_blank" rel="noopener noreferrer"
          className="text-xs px-2.5 py-1 rounded-lg bg-[#1ED760]/10 text-[#1ED760] hover:bg-[#1ED760]/20 transition font-medium">
          Spotify
        </a>
        <a href={ytmusic.url} target="_blank" rel="noopener noreferrer"
          className="text-xs px-2.5 py-1 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition font-medium">
          YT Music
        </a>
        <span className="text-xs text-gray-600 w-9 text-right tabular-nums">{score}%</span>
      </div>
    </div>
  );
}

function TrackCard({ track }: { track: Track }) {
  const isSpotify = track.source === "spotify";
  return (
    <a href={track.url} target="_blank" rel="noopener noreferrer"
      className="rounded-xl bg-[#111] border border-white/5 p-4 flex items-center gap-4 hover:bg-white/5 transition cursor-pointer">
      <div className="w-11 h-11 shrink-0">
        {track.thumbnail && (
          <img src={track.thumbnail} alt="" className="w-11 h-11 rounded-lg object-cover" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate text-white">{track.title || track.raw_title}</p>
        <p className="text-xs text-gray-500 truncate mt-0.5">{track.artist}</p>
      </div>
      <span className={`text-xs px-2.5 py-1 rounded-lg shrink-0 font-medium ${
        isSpotify
          ? "bg-[#1ED760]/10 text-[#1ED760]"
          : "bg-red-500/10 text-red-400"
      }`}>
        {isSpotify ? "Spotify" : "YT Music"}
      </span>
    </a>
  );
}
