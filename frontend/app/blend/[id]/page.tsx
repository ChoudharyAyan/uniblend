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
}

interface SessionStatus {
  blend_id: string;
  status: BlendStatus;
  spotify_connected: boolean;
  ytmusic_connected: boolean;
  result: BlendResult | null;
  error: string | null;
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

  // ── Handle OAuth redirect params ──────────────────────────────────────────
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

  // ── Poll blend status ─────────────────────────────────────────────────────
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

  // ── Connect platform ──────────────────────────────────────────────────────
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

  // ── Copy link ─────────────────────────────────────────────────────────────
  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (notFound) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-center">
        <p className="text-red-400 text-lg mb-4">Blend not found or expired.</p>
        <button onClick={() => router.push("/")} className="px-6 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 transition">
          Create a new blend
        </button>
      </div>
    );
  }

  if (!serverStatus) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400">Loading blend room…</p>
      </div>
    );
  }

  const { spotify_connected, ytmusic_connected, status, result, error } = serverStatus;
  const shareUrl = typeof window !== "undefined" ? window.location.href : "";

  // ── Phase: done ───────────────────────────────────────────────────────────
  if (status === "done" && result) {
    const { stats, matches, spotify_only, yt_only } = result;
    const tabs: { key: Tab; label: string; count: number }[] = [
      { key: "matches", label: "Matches", count: stats.matched },
      { key: "spotify_only", label: "Spotify only", count: stats.spotify_only },
      { key: "yt_only", label: "YouTube only", count: stats.yt_only },
    ];
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <button onClick={() => router.push("/")} className="text-sm text-gray-500 hover:text-gray-300 mb-6 inline-flex items-center gap-1 transition">
          ← New blend
        </button>
        <h1 className="text-3xl font-bold mb-1">Your Blend ✨</h1>
        <p className="text-gray-400 text-sm mb-8">
          {stats.total_spotify} Spotify tracks · {stats.total_yt} YouTube Music tracks
        </p>

        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="rounded-xl bg-violet-900/30 border border-violet-800 p-4 text-center">
            <div className="text-2xl font-bold text-violet-300">{stats.matched}</div>
            <div className="text-xs text-gray-400 mt-1">Matches</div>
          </div>
          <div className="rounded-xl bg-green-900/30 border border-green-800 p-4 text-center">
            <div className="text-2xl font-bold text-green-300">{stats.spotify_only}</div>
            <div className="text-xs text-gray-400 mt-1">Spotify only</div>
          </div>
          <div className="rounded-xl bg-red-900/30 border border-red-800 p-4 text-center">
            <div className="text-2xl font-bold text-red-300">{stats.yt_only}</div>
            <div className="text-xs text-gray-400 mt-1">YouTube only</div>
          </div>
        </div>

        <div className="flex gap-2 mb-6">
          {tabs.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${tab === t.key ? "bg-gray-700 text-white" : "text-gray-400 hover:text-gray-200"}`}>
              {t.label}
              <span className="ml-2 text-xs bg-gray-800 px-2 py-0.5 rounded-full">{t.count}</span>
            </button>
          ))}
        </div>

        <div className="space-y-2">
          {tab === "matches" && matches.map((m, i) => <MatchCard key={i} match={m} />)}
          {tab === "spotify_only" && spotify_only.map((t, i) => <TrackCard key={i} track={t} />)}
          {tab === "yt_only" && yt_only.map((t, i) => <TrackCard key={i} track={t} />)}
          {tab === "matches" && matches.length === 0 && (
            <p className="text-gray-500 text-center py-12">No matches found — very different tastes!</p>
          )}
        </div>
      </div>
    );
  }

  // ── Phase: error ──────────────────────────────────────────────────────────
  if (status === "error") {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-center">
        <p className="text-red-400 mb-4">{error ?? "Something went wrong computing the blend."}</p>
        <button onClick={() => router.push("/")} className="px-6 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 transition">
          Try again
        </button>
      </div>
    );
  }

  // ── Phase: computing ──────────────────────────────────────────────────────
  if (status === "computing") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-lg font-semibold">Blending your taste…</p>
        <p className="text-gray-500 text-sm">This takes about 10–20 seconds</p>
      </div>
    );
  }

  // ── Phase: waiting (one or both platforms not yet connected) ──────────────
  const availablePlatform: Platform | null =
    !spotify_connected ? "spotify" : !ytmusic_connected ? "ytmusic" : null;

  const platformLabel = (p: Platform) => (p === "spotify" ? "Spotify" : "YouTube Music");
  const platformColor = (p: Platform) => (p === "spotify" ? "green" : "red");

  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <button onClick={() => router.push("/")} className="text-sm text-gray-500 hover:text-gray-300 mb-8 inline-flex items-center gap-1 transition">
        ← Home
      </button>

      <h1 className="text-3xl font-bold mb-2">Blend Room</h1>
      <p className="text-gray-400 mb-10 text-sm">
        Both friends need to connect their platform. Share this link with your friend.
      </p>

      {/* Share link */}
      <div className="rounded-xl bg-gray-900 border border-gray-700 p-4 flex items-center gap-3 mb-10">
        <span className="text-gray-400 text-xs flex-1 truncate">{shareUrl}</span>
        <button onClick={copyLink}
          className="text-xs px-3 py-1.5 rounded-lg bg-violet-700 hover:bg-violet-600 transition font-medium shrink-0">
          {copied ? "Copied!" : "Copy link"}
        </button>
      </div>

      {/* Platform status cards */}
      <div className="grid grid-cols-2 gap-4 mb-10">
        {(["spotify", "ytmusic"] as Platform[]).map((p) => {
          const isConnected = p === "spotify" ? spotify_connected : ytmusic_connected;
          const isMine = myPlatform === p;
          const color = platformColor(p);
          return (
            <div key={p} className={`rounded-2xl border p-6 flex flex-col items-center gap-4 ${
              isConnected ? `border-${color}-800 bg-${color}-900/20` : "border-gray-800 bg-gray-900"
            }`}>
              <div className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl ${
                p === "spotify" ? "bg-green-500" : "bg-red-500"
              }`}>
                {p === "spotify" ? "🎵" : "🎶"}
              </div>
              <p className="font-semibold">{platformLabel(p)}</p>
              <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                isConnected
                  ? p === "spotify" ? "bg-green-900/60 text-green-400" : "bg-red-900/60 text-red-400"
                  : "bg-gray-800 text-gray-500"
              }`}>
                {isConnected ? "● Connected" : "○ Not connected"}
              </span>
              {!isConnected && (
                <button
                  onClick={() => handleConnect(p)}
                  disabled={connecting === p}
                  className={`w-full py-2 rounded-xl font-semibold text-sm transition disabled:opacity-60 ${
                    p === "spotify"
                      ? "bg-green-500 hover:bg-green-400 text-black"
                      : "bg-red-500 hover:bg-red-400 text-white"
                  }`}>
                  {connecting === p ? "Redirecting…" : `Connect ${platformLabel(p)}`}
                </button>
              )}
              {isConnected && isMine && (
                <p className="text-xs text-gray-500">You connected this</p>
              )}
              {isConnected && !isMine && (
                <p className="text-xs text-gray-500">Your friend connected this</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Waiting indicator */}
      {(spotify_connected || ytmusic_connected) && availablePlatform && (
        <div className="text-center text-gray-400 text-sm flex items-center justify-center gap-2">
          <div className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
          Waiting for your friend to connect {platformLabel(availablePlatform)}…
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MatchCard({ match }: { match: Match }) {
  const { spotify, ytmusic, score } = match;
  return (
    <div className="rounded-xl bg-gray-900 border border-gray-800 p-4 flex items-center gap-4">
      <div className="w-12 h-12 shrink-0">
        {spotify.thumbnail && (
          <img src={spotify.thumbnail} alt="" className="w-12 h-12 rounded-lg object-cover" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{spotify.title}</p>
        <p className="text-sm text-gray-400 truncate">{spotify.artist}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <a href={spotify.url} target="_blank" rel="noopener noreferrer"
          className="text-xs px-2 py-1 rounded bg-green-900/50 text-green-400 hover:bg-green-900 transition">
          Spotify
        </a>
        <a href={ytmusic.url} target="_blank" rel="noopener noreferrer"
          className="text-xs px-2 py-1 rounded bg-red-900/50 text-red-400 hover:bg-red-900 transition">
          YouTube
        </a>
        <span className="text-xs text-gray-500 w-10 text-right">{score}%</span>
      </div>
    </div>
  );
}

function TrackCard({ track }: { track: Track }) {
  const isSpotify = track.source === "spotify";
  return (
    <div className="rounded-xl bg-gray-900 border border-gray-800 p-4 flex items-center gap-4">
      <div className="w-12 h-12 shrink-0">
        {track.thumbnail && (
          <img src={track.thumbnail} alt="" className="w-12 h-12 rounded-lg object-cover" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{track.title || track.raw_title}</p>
        <p className="text-sm text-gray-400 truncate">{track.artist}</p>
      </div>
      <a href={track.url} target="_blank" rel="noopener noreferrer"
        className={`text-xs px-2 py-1 rounded shrink-0 transition ${
          isSpotify ? "bg-green-900/50 text-green-400 hover:bg-green-900" : "bg-red-900/50 text-red-400 hover:bg-red-900"
        }`}>
        {isSpotify ? "Spotify" : "YouTube"}
      </a>
    </div>
  );
}
