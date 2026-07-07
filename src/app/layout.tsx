import type { Metadata } from "next";
import { IBM_Plex_Sans, Newsreader } from "next/font/google";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "./auth";
import { SmartOpsProvider } from "./providers";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "SmartOps | Smart Building Operations",
  description:
    "Commercial smart-building operations dashboard demo with privacy-safe VLM/LLM insights.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${plexSans.variable} ${newsreader.variable} antialiased`}>
        <AuthProvider>
          <SmartOpsProvider>
            <AppShell>{children}</AppShell>
          </SmartOpsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}





