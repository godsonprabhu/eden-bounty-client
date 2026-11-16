import type { Metadata } from "next";
import { AdminAuthProvider } from "@/context/AdminAuthContext";

export const metadata: Metadata = {
  title: "Login",
  description: "Secure sign-in for EDEN BOUNTY administrators and customers.",
  alternates: { canonical: "/login" },
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  referrer: "no-referrer",
};

/** Provides the existing session-cookie auth context to the integrated login page. */
export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <AdminAuthProvider>{children}</AdminAuthProvider>;
}
