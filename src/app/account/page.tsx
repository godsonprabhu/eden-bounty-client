"use client";

import Link from "next/link";
import { usePortalAuth } from "@/context/PortalAuthContext";
import { OrdersTable } from "@/components/portal/OrderViews";
import { Empty, fmtDate, fmtDateTime, PageHeader, Panel, Resource, Stat, StatusBadge, Table, td, tdStrong, useResource } from "@/components/portal/ui";
import type { CustomerOverview } from "@/types/portal";

export default function AccountOverviewPage() {
  const { user } = usePortalAuth();
  const overview = useResource<CustomerOverview>("/customer/overview");

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title={`Welcome, ${user?.full_name ?? ""}`}
        intro="A summary of your enquiries and orders with EDEN BOUNTY. Only records belonging to your account are shown here."
      />
      <Resource state={overview} rows={4}>
        {(data) => (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Stat label="Enquiries" value={data.enquiries_total} detail={`${data.enquiries_open} open`} href="/account/enquiries" />
              <Stat label="Orders" value={data.orders_total} detail={`${data.orders_active} in progress`} href="/account/orders" />
              <Stat label="Company" value={<span className="text-base">{user?.company_name || "—"}</span>} />
              <Stat label="Last sign-in" value={<span className="text-base">{fmtDateTime(user?.last_login_at)}</span>} />
            </div>

            <Panel title="Recent orders" actions={<Link href="/account/orders" className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-brand hover:underline">All orders</Link>}>
              {data.recent_orders.length === 0 ? (
                <Empty title="No orders yet">Orders are created by our team after your enquiry has been reviewed and agreed.</Empty>
              ) : (
                <OrdersTable orders={data.recent_orders} hrefBase="/account/orders" />
              )}
            </Panel>

            <Panel title="Recent enquiries" actions={<Link href="/account/enquiries" className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-brand hover:underline">All enquiries</Link>}>
              {data.recent_enquiries.length === 0 ? (
                <Empty title="No enquiries linked to your account yet">
                  Enquiries appear here once our team has confirmed they belong to your account.{" "}
                  <Link href="/rfq" className="text-brand underline underline-offset-4">Submit a new enquiry</Link>.
                </Empty>
              ) : (
                <Table caption="Recent enquiries" head={["Reference", "Product", "Service", "Submitted", "Status"]}>
                  {data.recent_enquiries.map((e) => (
                    <tr key={e.id}>
                      <td className={tdStrong}>
                        <Link href={`/account/enquiries/${e.id}`} className="font-mono text-xs underline decoration-brand underline-offset-4 hover:text-brand">{e.reference_number}</Link>
                      </td>
                      <td className={td}>{e.product_focus}</td>
                      <td className={td}>{e.division.name}</td>
                      <td className={td + " whitespace-nowrap"}>{fmtDate(e.created_at)}</td>
                      <td className={td}><StatusBadge status={e.status} /></td>
                    </tr>
                  ))}
                </Table>
              )}
            </Panel>
          </>
        )}
      </Resource>
    </>
  );
}
