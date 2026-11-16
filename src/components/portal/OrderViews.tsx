"use client";

import Link from "next/link";
import { MapPin, Truck } from "lucide-react";
import type { OrderStatusEvent, OrderSummary, Shipment } from "@/types/portal";
import { Empty, fmtDate, fmtDateTime, fmtMoney, fmtQuantity, humanize, StatusBadge, Table, td, tdStrong } from "./ui";

export function OrdersTable({ orders, hrefBase }: { orders: OrderSummary[]; hrefBase: string }) {
  return (
    <Table caption="Orders" head={["Order", "Product", "Service", "Placed", "Total", "Status"]}>
      {orders.map((o) => (
        <tr key={o.id}>
          <td className={tdStrong}>
            <Link href={`${hrefBase}/${o.id}`} className="font-mono text-xs underline decoration-brand underline-offset-4 hover:text-brand">
              {o.reference_number}
            </Link>
          </td>
          <td className={td}>
            <span className="block text-ink">{o.product_description}</span>
            <span className="text-xs">{fmtQuantity(o.quantity, o.unit_of_measurement)}</span>
          </td>
          <td className={td}>{o.division.name}</td>
          <td className={td + " whitespace-nowrap"}>{fmtDate(o.created_at)}</td>
          <td className={td + " whitespace-nowrap tabular-nums"}>{fmtMoney(o.total_amount, o.currency)}</td>
          <td className={td}><StatusBadge status={o.status} /></td>
        </tr>
      ))}
    </Table>
  );
}

export function StatusTimeline({ events }: { events: OrderStatusEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-ink-muted">No status changes recorded yet.</p>;
  return (
    <ol className="space-y-5 border-l border-line pl-5">
      {events.map((e, i) => (
        <li key={`${e.created_at}-${i}`} className="relative">
          <span className="absolute -left-[1.6rem] top-1.5 h-2.5 w-2.5 rounded-full border border-brand bg-panel" aria-hidden="true" />
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={e.new_status} />
            <span className="text-xs text-ink-subtle">{fmtDateTime(e.created_at)}</span>
          </div>
          {e.note && <p className="mt-1.5 text-sm text-ink-muted">{e.note}</p>}
        </li>
      ))}
    </ol>
  );
}

export function ShipmentCard({ shipment, index, footer }: { shipment: Shipment; index: number; footer?: React.ReactNode }) {
  return (
    <article className="border border-line bg-panel-2 p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Truck className="h-4 w-4 text-brand" strokeWidth={1.5} aria-hidden="true" />
          Shipment {index + 1}
        </h3>
        <StatusBadge status={shipment.status} />
      </header>
      <dl className="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        {[
          ["Carrier", shipment.carrier],
          ["Tracking number", shipment.tracking_number],
          ["From", shipment.origin],
          ["To", shipment.destination],
          ["Shipped", shipment.shipped_at ? fmtDateTime(shipment.shipped_at) : null],
          ["Estimated delivery", shipment.estimated_delivery_on ? fmtDate(shipment.estimated_delivery_on) : null],
          ["Delivered", shipment.delivered_at ? fmtDateTime(shipment.delivered_at) : null],
        ].map(([k, v]) => (
          <div key={k as string} className="min-w-0">
            <dt className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-subtle">{k}</dt>
            <dd className="mt-0.5 text-ink [overflow-wrap:anywhere]">{v || "—"}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-5 border-t border-line pt-4">
        <p className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-subtle">Tracking updates</p>
        {shipment.events.length === 0 ? (
          <p className="mt-2 text-sm text-ink-muted">No tracking updates yet. Current status: {humanize(shipment.status)}.</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {shipment.events.map((ev) => (
              <li key={ev.id} className="flex gap-3 text-sm">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand" strokeWidth={1.5} aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-ink [overflow-wrap:anywhere]">{ev.description}</p>
                  <p className="text-xs text-ink-subtle">
                    {fmtDateTime(ev.occurred_at)}
                    {ev.location ? ` · ${ev.location}` : ""}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
      {footer && <div className="mt-5 border-t border-line pt-4">{footer}</div>}
    </article>
  );
}

export function NoShipments() {
  return <Empty title="No shipment yet">Shipment and tracking details appear here once your order has been dispatched.</Empty>;
}
