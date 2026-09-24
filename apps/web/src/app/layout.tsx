import type { Metadata } from "next";
import { IBM_Plex_Mono, Rajdhani, Share_Tech_Mono } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "@/components/providers/auth-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

// 3 font legacy (`newsroom.html`'s Google Fonts link) -- Rajdhani body,
// Share Tech Mono buat heading/stat-value, IBM Plex Mono buat data/mono
// label. Lihat docs/PROGRESS.md Fase 8 survei, keputusan #1 (Tailwind
// token, palet+font diekstrak dari CSS lama).
const rajdhani = Rajdhani({
  variable: "--font-rajdhani",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const shareTechMono = Share_Tech_Mono({
  variable: "--font-share-tech-mono",
  subsets: ["latin"],
  weight: "400",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["300", "400", "500"],
});

export const metadata: Metadata = {
  title: "CTI Platform",
  description: "Cyber threat intelligence platform",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      // `dark` KELAS TETAP nempel -- app ini dark-only (port persis tema
      // lama), gak ada toggle light/dark kayak app biasa.
      className={`dark ${rajdhani.variable} ${shareTechMono.variable} ${ibmPlexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-sans">
        <QueryProvider>
          <AuthProvider>
            <TooltipProvider>{children}</TooltipProvider>
          </AuthProvider>
        </QueryProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
