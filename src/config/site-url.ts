/**
 * Public canonical origin of the website.
 * Set NEXT_PUBLIC_SITE_URL at build time once the production domain is live (no trailing slash).
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://edenbounty.org").replace(/\/+$/, "");
