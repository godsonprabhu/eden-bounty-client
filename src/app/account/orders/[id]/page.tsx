"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { NoShipments, ShipmentCard, StatusTimeline } from "@/components/portal/OrderViews";
import { DefinitionList, fmtDateTime, fmtMoney, fmtQuantity, PageHeader, Panel, Resource, StatusBadge, useResource } from "@/components/portal/ui";
import type { OrderDetail } from "@/types/portal";

export default function OrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const order = useResource<OrderDetail>(`/customer/orders/${encodeURIComponent(id)}`);
  return (
    <>
      <Link href="/account/orders" className="inline-flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.16em] text-ink-muted hover:text-brand">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> All orders
      </Link>
      <Resource state={order}>
        {(o) => (
          <>
            <PageHeader eyebrow="Order" title={o.reference_number} intro={o.product_description} actions={<StatusBadge status={o.status} />} />
            <div className="grid gap-6 lg:grid-cols-5">
              <Panel title="Order details" className="lg:col-span-3">
                <DefinitionList
                  items={[
                    ["Service", o.division.name],
                    ["Product", o.product_description],
                    ["Quantity", fmtQuantity(o.quantity, o.unit_of_measurement)],
                    ["Order total", fmtMoney(o.total_amount, o.currency)],
                    ["Order date", fmtDateTime(o.created_at)],
                    ["From enquiry", o.enquiry_reference],
                    ["Note from our team", o.customer_note],
                  ]}
                />
              </Panel>
              <Panel title="Order history" className="lg:col-span-2">
                <StatusTimeline events={o.status_history} />
              </Panel>
            </div>
            <Panel title="Shipment and tracking">
              {o.shipments.length === 0 ? (
                <NoShipments />
              ) : (
                <div className="grid gap-5 lg:grid-cols-2">
                  {o.shipments.map((s, i) => (
                    <ShipmentCard key={s.id} shipment={s} index={i} />
                  ))}
                </div>
              )}
            </Panel>
          </>
        )}
      </Resource>
    </>
  );
}
