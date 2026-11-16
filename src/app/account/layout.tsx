import type { Metadata } from "next";
import { PortalShell } from "@/components/portal/PortalShell";

export const metadata: Metadata = {
  title: "My Account",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
};

const NAV = [
  { title: "Overview", href: "/account" },
  { title: "My Enquiries", href: "/account/enquiries" },
  { title: "My Orders", href: "/account/orders" },
  { title: "Track Orders", href: "/account/tracking" },
  { title: "Profile", href: "/account/profile" },
];

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <PortalShell area="customer" nav={NAV}>
      {children}
    </PortalShell>
  );
}
