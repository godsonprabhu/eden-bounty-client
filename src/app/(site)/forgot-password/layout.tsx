import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Forgot password",
  description: "Request a password reset link for an EDEN BOUNTY customer or investor account.",
  alternates: { canonical: "/forgot-password" },
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  referrer: "no-referrer",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
