"use client";

import { fmtMoney, Resource, Stat, useResource } from "@/components/portal/ui";
import type { PortalSummary } from "@/types/portal";

/** Totals for customers, investors, enquiries, orders and (for super administrators) investments. */
export function PortalSummaryCards() {
  const summary = useResource<PortalSummary>("/admin/dashboard/portal-summary");
  return (
    <section aria-label="Customers, investors and orders">
      <h2 className="mb-3 font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-subtle">Customers, investors &amp; orders</h2>
      <Resource state={summary} rows={1}>
        {(s) => {
          const open = Object.entries(s.orders_by_status).filter(([k]) => k !== "COMPLETED" && k !== "CANCELLED").reduce((n, [, v]) => n + v, 0);
          return (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <Stat label="Customers" value={s.total_customers} href="/admin/customers" />
              <Stat label="Investors" value={s.total_investors} href={s.investment_totals ? "/admin/investors" : undefined} />
              <Stat label="Enquiries" value={s.total_enquiries} href="/admin/enquiries" />
              <Stat label="Orders" value={s.total_orders} detail={`${open} in progress`} href="/admin/orders" />
              {s.investment_totals ? (
                s.investment_totals.length === 0 ? (
                  <Stat label="Investment overview" value={<span className="text-base">No records</span>} href="/admin/investors" />
                ) : (
                  s.investment_totals.map((t) => (
                    <Stat key={t.currency} label={`Invested (${t.currency})`} value={<span className="text-lg">{fmtMoney(t.total, t.currency)}</span>} detail={`${s.investments_count} record${s.investments_count === 1 ? "" : "s"} · active ${fmtMoney(t.active_total, t.currency)}`} href="/admin/investors" />
                  ))
                )
              ) : (
                <Stat label="Investment overview" value={<span className="text-base">Restricted</span>} detail="Super administrators only" />
              )}
            </div>
          );
        }}
      </Resource>
    </section>
  );
}
