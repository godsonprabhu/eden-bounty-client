"use client";

import { OrdersTable } from "@/components/portal/OrderViews";
import { Empty, PageHeader, Panel, Resource, useResource } from "@/components/portal/ui";
import type { OrderDetail } from "@/types/portal";

export default function MyOrdersPage() {
  const orders = useResource<OrderDetail[]>("/customer/orders");
  return (
    <>
      <PageHeader eyebrow="My Orders" title="Your orders" intro="Every order our team has created for your account, newest first. Open an order for its full history." />
      <Panel>
        <Resource
          state={orders}
          isEmpty={(d) => d.length === 0}
          empty={<Empty title="No orders yet">Orders are created by our team once an enquiry has been reviewed and its terms agreed.</Empty>}
        >
          {(rows) => <OrdersTable orders={rows} hrefBase="/account/orders" />}
        </Resource>
      </Panel>
    </>
  );
}
