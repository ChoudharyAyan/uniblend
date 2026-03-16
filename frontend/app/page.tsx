"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

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
    <div className="max-w-3xl mx-auto px-6 py-24 text-center">
      {/* Hero */}
      <h1 className="text-6xl font-extrabold tracking-tight mb-4">
        Uni<span className="text-violet-400">Blend</span>
      </h1>
      <p className="text-xl text-gray-400 mb-4 max-w-xl mx-auto">
        Two friends. Two platforms. One playlist.
      </p>
      <p className="text-gray-500 mb-12 max-w-lg mx-auto">
        One of you is on Spotify, the other on YouTube Music?
        Create a blend, share the link, and discover what you both listen to.
      </p>

      {/* How it works */}
      <div className="grid grid-cols-3 gap-6 mb-14 text-sm">
        {[
          { step: "1", title: "Create", desc: "One friend creates a blend and gets a shareable link." },
          { step: "2", title: "Connect", desc: "Each friend connects their own platform — Spotify or YouTube Music." },
          { step: "3", title: "Discover", desc: "See what you have in common and what's unique to each of you." },
        ].map((s) => (
          <div key={s.step} className="rounded-2xl bg-gray-900 border border-gray-800 p-5">
            <div className="w-8 h-8 rounded-full bg-violet-700 text-white text-sm font-bold flex items-center justify-center mx-auto mb-3">
              {s.step}
            </div>
            <p className="font-semibold mb-1">{s.title}</p>
            <p className="text-gray-500 text-xs leading-relaxed">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* CTA */}
      <button
        onClick={handleCreate}
        disabled={loading}
        className="px-12 py-4 rounded-2xl bg-violet-600 hover:bg-violet-500 font-bold text-lg transition shadow-xl disabled:opacity-60"
      >
        {loading ? "Creating blend…" : "Create a Blend"}
      </button>
    </div>
  );
}
