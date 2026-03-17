"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

function SpotifyMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 496 512" aria-label="Spotify">
      <path fill="#1ED760" d="M248 8C111.1 8 0 119.1 0 256s111.1 248 248 248 248-111.1 248-248S384.9 8 248 8zm100.7 364.9c-4.2 0-6.8-1.3-10.7-3.6-62.4-37.6-135-39.2-206.7-24.5-3.9 1-9 2.6-11.9 2.6-9.7 0-15.8-7.7-15.8-15.8 0-10.3 6.1-15.2 13.6-16.8 81.9-18.1 165.6-16.5 237 26.2 6.1 3.9 9.7 7.4 9.7 16.5s-7.1 15.4-15.2 15.4zm26.9-65.6c-5.2 0-8.7-2.3-12.3-4.2-62.5-37-155.7-51.9-238.6-29.4-4.8 1.3-7.4 2.6-11.9 2.6-10.7 0-19.4-8.7-19.4-19.4s5.2-17.8 15.5-20.7c27.8-7.8 56.2-13.6 97.8-13.6 64.9 0 127.6 16.1 177 45.5 8.1 4.5 11.3 11 11.3 19.4 0 10.7-8.7 19.8-19.4 19.8zm31-76.2c-5.2 0-8.4-1.3-12.9-3.9-71.2-42.5-198.5-52.7-280.9-29.7-3.9 1-8.1 2.6-12.9 2.6-13.2 0-23.3-10.3-23.3-23.6 0-13.6 8.4-21.3 17.4-23.9 35.2-10.3 74.6-15.2 117.5-15.2 73 0 149.5 15.2 205.4 47.8 7.8 4.5 12.9 10.7 12.9 22.6 0 13.2-10.3 23.3-23.2 23.3z"/>
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
        <div className="flex items-center gap-4 mb-8">
          <SpotifyMark size={44} />
          <div className="w-8 h-px bg-gradient-to-r from-green-500/40 via-gray-600 to-red-500/40" />
          <YTMusicMark size={44} />
        </div>

        {/* Hero text */}
        <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-center mb-3">
          Uni<span className="text-violet-400">Blend</span>
        </h1>
        <p className="text-base sm:text-xl text-gray-400 font-light text-center mb-2">
          Two friends. Two platforms. One shared taste.
        </p>
        <p className="text-gray-600 text-sm text-center max-w-sm leading-relaxed mb-10">
          One on Spotify, the other on YouTube Music?
          Find out what you both love.
        </p>

        {/* Steps */}
        <div className="w-full max-w-3xl mb-10">
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
