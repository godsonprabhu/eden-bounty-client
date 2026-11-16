"use client";

import Link from "next/link";
import { usePortalAuth } from "@/context/PortalAuthContext";
import { InvestmentsTable } from "@/components/portal/InvestmentsTable";
import { Empty, fmtMoney, humanize, PageHeader, Panel, Resource, Stat, StatusBadge, useResource } from "@/components/portal/ui";
import type { InvestorOverview } from "@/types/portal";

export default function InvestorOverviewPage() {
  const { user } = usePortalAuth();
  const overview = useResource<InvestorOverview>("/investor/overview");

  return (
    <>
      <PageHeader
        eyebrow="Investment overview"
        title={`Welcome, ${user?.full_name ?? ""}`}
        intro="A summary of the investments recorded against your account. Figures are the amounts recorded by the company; they are not valuations, returns or projections."
      />
      <Resource state={overview} rows={4}>
        {(data) =>
          data.investments_count === 0 ? (
            <Panel>
              <Empty title="No investment records yet">Records appear here once the company has entered them against your account.</Empty>
            </Panel>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {data.totals.map((t) => (
                  <Stat key={t.currency} label={`Total invested (${t.currency})`} value={fmtMoney(t.total, t.currency)} detail={`Active: ${fmtMoney(t.active_total, t.currency)}`} />
                ))}
                <Stat label="Investment records" value={data.investments_count} href="/investors/portal/investments" />
                <Stat label="Services invested in" value={new Set(data.allocation.map((a) => a.division.id)).size} />
              </div>

              <div className="grid gap-6 lg:grid-cols-5">
                <Panel title="Investment allocation" description="Share of your recorded total, by business service. Cancelled records are excluded." className="lg:col-span-3">
                  <ul className="space-y-5">
                    {data.allocation.map((a) => (
                      <li key={`${a.currency}-${a.division.id}`}>
                        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
                          <span className="font-semibold text-ink">{a.division.name}</span>
                          <span className="tabular-nums text-ink-muted">
                            {fmtMoney(a.amount, a.currency)} · {a.share_percent}%
                          </span>
                        </div>
                        <div className="mt-2 h-2 w-full bg-panel-2" role="img" aria-label={`${a.division.name}: ${a.share_percent} percent of ${a.currency} total`}>
                          <div className="h-full bg-brand" style={{ width: `${Math.min(100, Number(a.share_percent))}%` }} />
                        </div>
                        <p className="mt-1 text-xs text-ink-subtle">
                          {a.division.code} · {a.investments} record{a.investments === 1 ? "" : "s"}
                        </p>
                      </li>
                    ))}
                  </ul>
                </Panel>
                <Panel title="Investment status" className="lg:col-span-2">
                  <ul className="divide-y divide-line">
                    {Object.entries(data.status_counts)
                      .filter(([, n]) => n > 0)
                      .map(([s, n]) => (
                        <li key={s} className="flex items-center justify-between py-3 text-sm">
                          <StatusBadge status={s} label={humanize(s)} />
                          <span className="tabular-nums text-ink">{n}</span>
                        </li>
                      ))}
                  </ul>
                </Panel>
              </div>

              <Panel title="Recent investment history" actions={<Link href="/investors/portal/investments" className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-brand hover:underline">Full history</Link>}>
                <InvestmentsTable investments={data.recent_investments} />
              </Panel>
            </>
          )
        }
      </Resource>
    </>
  );
}
