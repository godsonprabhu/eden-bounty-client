"use client";

import Link from "next/link";
import { ShipmentCard } from "@/components/portal/OrderViews";
import { Empty, fmtDate, humanize, PageHeader, Panel, Resource, StatusBadge, useResource } from "@/components/portal/ui";
import type { OrderDetail } from "@/types/portal";

const FINISHED = new Set(["COMPLETED", "CANCELLED"]);

export default function TrackOrdersPage() {
  const orders = useResource<OrderDetail[]>("/customer/orders");
  return (
    <>
      <PageHeader eyebrow="Track Orders" title="Order tracking" intro="Processing status, shipment details and tracking updates for your orders that are still in progress." />
      <Resource state={orders}>
        {(rows) => {
          const active = rows.filter((o) => !FINISHED.has(o.status));
          if (active.length === 0) {
            return (
              <Panel>
                <Empty title="Nothing to track right now">
                  You have no orders in progress. Completed and cancelled orders stay available under{" "}
                  <Link href="/account/orders" className="text-brand underline underline-offset-4">My Orders</Link>.
                </Empty>
              </Panel>
            );
          }
          return (
            <div className="space-y-6">
              {active.map((o) => (
                <Panel
                  key={o.id}
                  title={`${o.reference_number} — ${o.product_description}`}
                  description={`Placed ${fmtDate(o.created_at)} · ${o.division.name}`}
                  actions={
                    <>
                      <StatusBadge status={o.status} />
                      <Link href={`/account/orders/${o.id}`} className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-brand hover:underline">Order details</Link>
                    </>
                  }
                >
                  <p className="text-sm text-ink-muted">
                    Processing status: <span className="font-semibold text-ink">{humanize(o.status)}</span>
                    {o.status_history[0]?.note ? ` — ${o.status_history[0].note}` : ""}
                  </p>
                  {o.shipments.length === 0 ? (
                    <p className="mt-3 text-sm text-ink-muted">No shipment has been recorded yet. Tracking details will appear here once the order is dispatched.</p>
                  ) : (
                    <div className="mt-5 grid gap-5 lg:grid-cols-2">
                      {o.shipments.map((s, i) => (
                        <ShipmentCard key={s.id} shipment={s} index={i} />
                      ))}
                    </div>
                  )}
                </Panel>
              ))}
            </div>
          );
        }}
      </Resource>
    </>
  );
}
