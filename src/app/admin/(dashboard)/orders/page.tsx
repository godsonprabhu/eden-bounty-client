"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { OrderCreateDialog } from "@/components/admin/portal/OrderCreateDialog";
import { Button, Empty, Field, fmtDate, fmtMoney, humanize, PageHeader, Panel, Resource, StatusBadge, Table, td, tdStrong, useResource } from "@/components/portal/ui";
import { ORDER_STATUSES, type AdminOrderSummary } from "@/types/portal";

export default function AdminOrdersPage() {
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const orders = useResource<AdminOrderSummary[]>(`/admin/orders${status ? `?status=${status}` : ""}`);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Order management"
        title="Orders"
        intro="Orders are created by administrators, usually from a reviewed enquiry. Customers can view and track their orders but cannot change them."
        actions={<Button onClick={() => setOpen(true)}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> New order</Button>}
      />
      <Panel>
        <Field
          label="Filter by status"
          as="select"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: "", label: "All statuses" }, ...ORDER_STATUSES.map((s) => ({ value: s, label: humanize(s) }))]}
          className="mb-5 max-w-xs"
        />
        <Resource state={orders} isEmpty={(d) => d.length === 0} empty={<Empty title={status ? "No orders with this status" : "No orders yet"}>{!status && "Create an order here, or convert an enquiry from its record."}</Empty>}>
          {(rows) => (
            <Table caption="Orders" head={["Order", "Customer", "Product", "Service", "Placed", "Total", "Status"]}>
              {rows.map((o) => (
                <tr key={o.id}>
                  <td className={tdStrong}>
                    <Link href={`/admin/orders/${o.id}`} className="font-mono text-xs underline decoration-brand underline-offset-4 hover:text-brand">{o.reference_number}</Link>
                  </td>
                  <td className={td}>
                    <Link href={`/admin/customers/${o.customer.id}`} className="text-ink hover:text-brand">{o.customer.full_name}</Link>
                    <span className="block text-xs">{o.customer.company_name || o.customer.email}</span>
                  </td>
                  <td className={td}>{o.product_description}</td>
                  <td className={td}>{o.division.name}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtDate(o.created_at)}</td>
                  <td className={td + " whitespace-nowrap tabular-nums"}>{fmtMoney(o.total_amount, o.currency)}</td>
                  <td className={td}><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Resource>
      </Panel>
      <OrderCreateDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
