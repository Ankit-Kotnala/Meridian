import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  ),
  title: {
    default: "CareerOS — Your career. Verified. Elevated.",
    template: "%s · CareerOS",
  },
  description:
    "An evidence-backed career application operating system for resume health, role readiness, job matching, and application workflow.",
  applicationName: "CareerOS",
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
  colorScheme: "light",
  themeColor: "#071a39",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a
          className="sr-only fixed left-4 top-4 z-[100] rounded-lg bg-white px-4 py-2 font-bold text-foreground shadow-xl focus:not-sr-only"
          href="#main-content"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
