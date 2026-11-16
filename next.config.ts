import type { NextConfig } from "next";

// Baseline security headers (HSTS is added by the TLS-terminating proxy in production).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

// Pages that handle credentials or single-use invitation/reset links.
const AUTH_PAGES = ["/login", "/investors/login", "/forgot-password", "/reset-password", "/register", "/verify-email"];

const previewDevOrigins = (() => {
  const origin = process.env.PREVIEW_ORIGIN;
  if (!origin) return [];
  try {
    const parsed = new URL(origin);
    return [parsed.host];
  } catch {
    return [];
  }
})();

const nextConfig: NextConfig = {
  ...(process.env.NODE_ENV === "development"
    ? { allowedDevOrigins: ["192.168.0.123", ...previewDevOrigins] }
    : {}),
  reactStrictMode: true,
  // Self-contained server bundle for the production Docker image (no effect on `next dev`).
  output: "standalone",
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // Authentication pages send no Referer at all (the last matching rule wins for a header).
      ...AUTH_PAGES.map((source) => ({ source, headers: [{ key: "Referrer-Policy", value: "no-referrer" }] })),
    ];
  },
  poweredByHeader: false,
  compress: true,
  images: {
    formats: ["image/avif", "image/webp"],
  },
  async redirects() {
    return [
      // The console sign-in now lives at /login; keep old bookmarks working.
      { source: "/admin/login", destination: "/login", permanent: false },
      // "Contact" is the Request for Quotation page. Query strings (e.g. ?division=) are carried over.
      { source: "/contact", destination: "/rfq", permanent: true },
      // The Operations page was withdrawn (CR-C3). Its source files are kept but no longer reachable.
      { source: "/operations", destination: "/services", permanent: false },
      // Direct alias for robotics to dedicated drone aerial platform service
      { source: "/services/robotics", destination: "/services/agricultural-drones", permanent: false },
      { source: "/services/drone-solutions", destination: "/services/agricultural-drones", permanent: false },
      { source: "/services/drones", destination: "/services/agricultural-drones", permanent: false },
      // Duplicate building-promotions route forwards to canonical construction service
      { source: "/services/building-promotions", destination: "/services/construction", permanent: false },
      // Withdrawn lubricants routes redirect back to main services catalogue
      { source: "/services/lubricants", destination: "/services", permanent: false },
      { source: "/services/industrial-lubricants", destination: "/services", permanent: false },
      // Withdrawn shisha routes redirect back to main services catalogue
      { source: "/services/shisha-tobacco-trading", destination: "/services", permanent: false },
      { source: "/services/shisha", destination: "/services", permanent: false },
      // Withdrawn Axe Oil routes redirect back to main services catalogue
      { source: "/services/axe-oil", destination: "/services", permanent: false },
      { source: "/services/axe-oil-trading", destination: "/services", permanent: false },
    ];
  },
  async rewrites() {
    const backendUrl = process.env.INTERNAL_BACKEND_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
