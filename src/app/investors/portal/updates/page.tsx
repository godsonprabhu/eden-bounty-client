"use client";

import { Empty, fmtDate, PageHeader, Panel, Resource, useResource } from "@/components/portal/ui";
import type { InvestorUpdate } from "@/types/portal";

export default function InvestorUpdatesPage() {
  const updates = useResource<InvestorUpdate[]>("/investor/updates");
  return (
    <>
      <PageHeader eyebrow="Updates" title="Investor updates" intro="Announcements from the company to investors, and updates addressed to you." />
      <Resource
        state={updates}
        isEmpty={(d) => d.length === 0}
        empty={
          <Panel>
            <Empty title="No updates have been published yet" />
          </Panel>
        }
      >
        {(rows) => (
          <div className="space-y-5">
            {rows.map((u) => (
              <article key={u.id} className="border border-line bg-panel p-6">
                <p className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-subtle">
                  {fmtDate(u.published_at ?? u.created_at)} · {u.investor_id ? "For you" : "All investors"}
                </p>
                <h2 className="mt-2 text-lg font-semibold text-ink [overflow-wrap:anywhere]">{u.title}</h2>
                <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink-muted [overflow-wrap:anywhere]">{u.body}</p>
              </article>
            ))}
          </div>
        )}
      </Resource>
    </>
  );
}
