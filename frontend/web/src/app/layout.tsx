import type { Metadata, Viewport } from "next";
import { Inter_Tight, Space_Grotesk } from "next/font/google";
import type { ReactNode } from "react";

import { ThemeScript } from "@/shared/theme/theme-script";

import "./globals.css";

const sans = Inter_Tight({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans-loaded",
});

const display = Space_Grotesk({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display-loaded",
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  ),
  title: {
    default: "Meridian — Build from career truth",
    template: "%s · Meridian",
  },
  description:
    "An evidence-backed career operating system for maintaining a structured career record and creating grounded application materials.",
  applicationName: "Meridian",
  category: "productivity",
  keywords: [
    "career profile",
    "resume health",
    "job readiness",
    "career evidence",
    "application workflow",
  ],
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7f3" },
    { media: "(prefers-color-scheme: dark)", color: "#0a1310" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html
      className={`${sans.variable} ${display.variable}`}
      lang="en"
      suppressHydrationWarning
    >
      <head>
        <ThemeScript />
      </head>
      <body>
        <a className="skip-link sr-only focus:not-sr-only" href="#main-content">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
