import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UniBlend",
  description: "Blend your Spotify and YouTube Music taste",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-950 text-white">
        <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-10">
          <div className="max-w-5xl mx-auto px-6 h-14 flex items-center">
            <span className="text-xl font-bold tracking-tight">
              Uni<span className="text-violet-400">Blend</span>
            </span>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
