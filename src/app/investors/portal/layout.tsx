import type { Metadata } from "next";
import { PortalShell } from "@/components/portal/PortalShell";

export const metadata: Metadata = {
  title: "Investor Portal",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
};

const NAV = [
  { title: "Overview", href: "/investors/portal" },
  { title: "Investments", href: "/investors/portal/investments" },
  { title: "Documents", href: "/investors/portal/documents" },
  { title: "Updates", href: "/investors/portal/updates" },
  { title: "Profile", href: "/investors/portal/profile" },
];

export default function InvestorPortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <PortalShell area="investor" nav={NAV}>
      {children}
    </PortalShell>
  );
}
