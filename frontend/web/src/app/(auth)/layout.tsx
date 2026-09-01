import type { Metadata } from "next";
import { Source_Serif_4 } from "next/font/google";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

const authDisplay = Source_Serif_4({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-auth-display",
  display: "swap",
});

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <div className={authDisplay.variable}>{children}</div>;
}
