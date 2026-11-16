"use client";

import { useAdminAuth } from "@/context/AdminAuthContext";
import { AccountsList } from "@/components/admin/portal/AccountsList";
import { InvestorAnnouncements } from "@/components/admin/portal/InvestorAnnouncements";

export default function AdminInvestorsPage() {
  const { hasRole } = useAdminAuth();
  return (
    <div className="space-y-6">
      <AccountsList role="INVESTOR" />
      {hasRole("SUPER_ADMIN") && <InvestorAnnouncements />}
    </div>
  );
}
