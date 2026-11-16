"use client";

import Link from "next/link";
import { Empty, fmtDate, PageHeader, Panel, Resource, StatusBadge, Table, td, tdStrong, useResource } from "@/components/portal/ui";
import type { CustomerEnquirySummary } from "@/types/portal";

export default function MyEnquiriesPage() {
  const enquiries = useResource<CustomerEnquirySummary[]>("/customer/enquiries");
  return (
    <>
      <PageHeader
        eyebrow="My Enquiries"
        title="Your enquiries"
        intro="Requests for quotation that our team has confirmed belong to your account, with their current status."
        actions={<Link href="/rfq" className="inline-flex min-h-10 items-center bg-brand px-4 text-xs font-semibold uppercase tracking-[0.14em] text-brand-ink hover:bg-brand-hover">New enquiry</Link>}
      />
      <Panel>
        <Resource
          state={enquiries}
          isEmpty={(d) => d.length === 0}
          empty={
            <Empty title="No enquiries to show">
              If you have submitted an enquiry and do not see it here, it has not yet been linked to your account. Our team links enquiries after confirming who submitted them.
            </Empty>
          }
        >
          {(rows) => (
            <Table caption="Your enquiries" head={["Reference", "Product", "Service", "Submitted", "Last update", "Status"]}>
              {rows.map((e) => (
                <tr key={e.id}>
                  <td className={tdStrong}>
                    <Link href={`/account/enquiries/${e.id}`} className="font-mono text-xs underline decoration-brand underline-offset-4 hover:text-brand">{e.reference_number}</Link>
                  </td>
                  <td className={td}>{e.product_focus}</td>
                  <td className={td}>{e.division.name}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtDate(e.created_at)}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtDate(e.updated_at)}</td>
                  <td className={td}><StatusBadge status={e.status} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Resource>
      </Panel>
    </>
  );
}
