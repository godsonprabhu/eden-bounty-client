"use client";

import { InvestmentsTable } from "@/components/portal/InvestmentsTable";
import { Empty, PageHeader, Panel, Resource, useResource } from "@/components/portal/ui";
import type { Investment } from "@/types/portal";

export default function InvestmentsPage() {
  const investments = useResource<Investment[]>("/investor/investments");
  return (
    <>
      <PageHeader eyebrow="Investments" title="Investment history" intro="Every investment recorded against your account, with the business division, date, amount and current status." />
      <Panel>
        <Resource state={investments} isEmpty={(d) => d.length === 0} empty={<Empty title="No investment records yet" />}>
          {(rows) => <InvestmentsTable investments={rows} />}
        </Resource>
      </Panel>
    </>
  );
}
