"use client";

import { use } from "react";
import { AccountDetail } from "@/components/admin/portal/AccountDetail";

export default function AdminCustomerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <AccountDetail role="CUSTOMER" id={id} />;
}
