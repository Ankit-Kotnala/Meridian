import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  ),
  title: {
    default: "CareerOS — Build from career truth",
    template: "%s · CareerOS",
  },
  description:
    "An evidence-backed career operating system for maintaining a structured career record and creating grounded application materials.",
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
  themeColor: "#132d24",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link sr-only focus:not-sr-only" href="#main-content">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
