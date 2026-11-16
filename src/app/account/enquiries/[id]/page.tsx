"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, MessageSquareText, RefreshCw } from "lucide-react";
import { OrdersTable } from "@/components/portal/OrderViews";
import { DefinitionList, Empty, fmtDateTime, fmtQuantity, PageHeader, Panel, Resource, StatusBadge, useResource } from "@/components/portal/ui";
import type { CustomerEnquiryDetail } from "@/types/portal";

export default function EnquiryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const enquiry = useResource<CustomerEnquiryDetail>(`/customer/enquiries/${encodeURIComponent(id)}`);
  return (
    <>
      <Link href="/account/enquiries" className="inline-flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.16em] text-ink-muted hover:text-brand">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> All enquiries
      </Link>
      <Resource state={enquiry}>
        {(e) => (
          <>
            <PageHeader eyebrow="Enquiry" title={e.reference_number} intro={e.product_focus} actions={<StatusBadge status={e.status} />} />
            <div className="grid gap-6 lg:grid-cols-5">
              <Panel title="Enquiry details" className="lg:col-span-3">
                <DefinitionList
                  items={[
                    ["Service", e.division.name],
                    ["Product", e.product_focus],
                    ["Quantity", fmtQuantity(e.quantity, e.unit_of_measurement)],
                    ["Specifications", e.specifications],
                    ["Incoterm", e.preferred_incoterm],
                    ["Destination port", e.target_destination_port],
                    ["Your notes", e.additional_notes],
                    ["Submitted", fmtDateTime(e.created_at)],
                  ]}
                />
              </Panel>
              <Panel title="Updates" description="Status changes and messages from our team." className="lg:col-span-2">
                {e.updates.length === 0 ? (
                  <Empty title="No updates yet">We will post progress here as your enquiry is reviewed.</Empty>
                ) : (
                  <ol className="space-y-4">
                    {e.updates.map((u, i) => (
                      <li key={`${u.created_at}-${i}`} className="flex gap-3 text-sm">
                        {u.kind === "MESSAGE" ? (
                          <MessageSquareText className="mt-0.5 h-4 w-4 shrink-0 text-brand" strokeWidth={1.5} aria-hidden="true" />
                        ) : (
                          <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-ink-subtle" strokeWidth={1.5} aria-hidden="true" />
                        )}
                        <div className="min-w-0">
                          <p className="whitespace-pre-line text-ink [overflow-wrap:anywhere]">{u.text}</p>
                          <p className="text-xs text-ink-subtle">{fmtDateTime(u.created_at)}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </Panel>
            </div>
            <Panel title="Orders from this enquiry">
              {e.orders.length === 0 ? (
                <Empty title="No order has been created from this enquiry yet" />
              ) : (
                <OrdersTable orders={e.orders} hrefBase="/account/orders" />
              )}
            </Panel>
          </>
        )}
      </Resource>
    </>
  );
}
