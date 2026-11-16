import type { Metadata } from "next";
import { AdminAuthProvider } from "@/context/AdminAuthContext";

export const metadata: Metadata = {
  title: "EDEN BOUNTY — Central Operations Console",
  description: "Secure administrative management console for EDEN BOUNTY Sdn. Bhd.",
  robots: {
    index: false,
    follow: false,
    googleBot: {
      index: false,
      follow: false,
    },
  },
};

export default function AdminRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminAuthProvider>{children}</AdminAuthProvider>;
}
