"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

function SpotifyMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 168 168" aria-label="Spotify">
      <circle cx="84" cy="84" r="84" fill="#1ED760" />
      <path
        fill="white"
        d="M119.3 113.6c-1.9 3.1-5.9 4-9 2.1-24.6-15-55.6-18.4-92.1-10.1-3.5.8-7-1.4-7.8-4.9-.8-3.5 1.4-7 4.9-7.8 39.9-9.1 74.2-5.2 101.9 11.7 3.1 1.9 4 5.9 2.1 9zm11.3-24.1c-2.4 3.8-7.4 5-11.2 2.6-28.2-17.3-71.2-22.3-104.6-12.2-4.3 1.3-8.9-1.1-10.3-5.5-1.3-4.3 1.1-8.9 5.5-10.3 38.1-11.6 85.5-5.9 117.9 13.9 3.8 2.4 5 7.4 2.7 11.5zm1-24.5c-33.8-20.1-89.7-21.9-122-12.1-5.2 1.6-10.7-1.4-12.2-6.6-1.6-5.2 1.4-10.7 6.6-12.2 37.1-11.3 98.8-9.1 137.8 14 4.6 2.7 6.1 8.7 3.4 13.3-2.8 4.6-8.7 6.1-13.6 3.6z"
      />
    </svg>
  );
}

function YTMusicMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-label="YouTube Music">
      <circle cx="24" cy="24" r="24" fill="#FF0000" />
      <circle cx="24" cy="24" r="12" fill="white" />
      <polygon points="21,18 31,24 21,30" fill="#FF0000" />
    </svg>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    setLoading(true);
    try {
      const { data } = await api.post<{ blend_id: string }>("/blend/session");
      router.push(`/blend/${data.blend_id}`);
    } catch {
      alert("Could not reach the backend. Make sure it is running on port 8000.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-24">

        {/* Platform logos */}
        <div className="flex items-center gap-4 mb-12">
          <div className="rounded-2xl p-1 shadow-lg shadow-green-900/30">
            <SpotifyMark size={48} />
          </div>
          <div className="w-8 h-px bg-gradient-to-r from-green-500/40 via-gray-600 to-red-500/40" />
          <div className="rounded-2xl p-1 shadow-lg shadow-red-900/30">
            <YTMusicMark size={48} />
          </div>
        </div>

        {/* Hero text */}
        <h1 className="text-6xl sm:text-7xl font-bold tracking-tight text-center mb-4">
          Uni<span className="text-violet-400">Blend</span>
        </h1>
        <p className="text-xl sm:text-2xl text-gray-400 font-light text-center mb-3">
          Two friends. Two platforms. One shared taste.
        </p>
        <p className="text-gray-600 text-center max-w-sm leading-relaxed mb-16">
          One of you uses Spotify, the other YouTube Music?
          Find out what you both love.
        </p>

        {/* Steps */}
        <div className="w-full max-w-3xl mb-16">
          <div className="grid grid-cols-3 gap-px bg-white/5 rounded-2xl overflow-hidden border border-white/5">
            {[
              {
                badge: <div className="flex items-center gap-1.5"><SpotifyMark size={18} /><YTMusicMark size={18} /></div>,
                title: "Create",
                desc: "Start a blend room and get a shareable link.",
              },
              {
                badge: (
                  <svg className="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                ),
                title: "Connect",
                desc: "Each friend links their own platform privately.",
              },
              {
                badge: (
                  <svg className="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                  </svg>
                ),
                title: "Discover",
                desc: "See your shared songs and what makes you unique.",
              },
            ].map((s, i) => (
              <div key={i} className="bg-[#111] px-6 py-8 flex flex-col items-center text-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">
                  {s.badge}
                </div>
                <p className="font-semibold text-white text-sm">{s.title}</p>
                <p className="text-gray-500 text-xs leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={handleCreate}
          disabled={loading}
          className="px-14 py-4 rounded-full bg-violet-600 hover:bg-violet-500 font-semibold text-base transition-all duration-200 shadow-xl shadow-violet-900/30 disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98]"
        >
          {loading ? "Creating blend…" : "Create a Blend"}
        </button>
        <p className="text-gray-700 text-xs mt-4">Free · No account required</p>
      </div>
    </div>
  );
}
