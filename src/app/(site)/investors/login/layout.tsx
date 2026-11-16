import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Investor Login",
  description: "Secure sign-in for existing EDEN BOUNTY investors.",
  alternates: { canonical: "/investors/login" },
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  referrer: "no-referrer",
};

export default function InvestorLoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
