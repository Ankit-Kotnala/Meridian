import type { NextConfig } from "next";
import { resolve } from "node:path";

const developmentScriptPolicy =
  process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : "";

function uploadOrigin(): string {
  const configured =
    process.env.NEXT_PUBLIC_UPLOAD_ORIGIN ?? "http://localhost:9000";
  const value = new URL(configured);
  const localHttp =
    value.protocol === "http:" &&
    new Set(["localhost", "127.0.0.1", "[::1]"]).has(value.hostname);
  if (
    value.origin !== configured.replace(/\/$/, "") ||
    (value.protocol !== "https:" && !localHttp) ||
    value.username ||
    value.password
  ) {
    throw new Error(
      "NEXT_PUBLIC_UPLOAD_ORIGIN must be one exact HTTPS origin or a local HTTP origin.",
    );
  }
  return value.origin;
}

const resolvedUploadOrigin = uploadOrigin();

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "object-src 'none'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      `script-src 'self' 'unsafe-inline'${developmentScriptPolicy}`,
      `connect-src 'self' ${resolvedUploadOrigin}`,
      ...(resolvedUploadOrigin.startsWith("https:")
        ? ["upgrade-insecure-requests"]
        : []),
    ].join("; "),
  },
];

const workspaceRoot = resolve(import.meta.dirname, "../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: workspaceRoot,
  experimental: { useTypeScriptCli: true },
  turbopack: { root: workspaceRoot },
  poweredByHeader: false,
  reactStrictMode: true,
  transpilePackages: ["@careeros/ui"],
  experimental: {
    useTypeScriptCli: true,
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
