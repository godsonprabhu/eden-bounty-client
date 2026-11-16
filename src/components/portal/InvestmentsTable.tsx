"use client";

import type { Investment } from "@/types/portal";
import { fmtDate, fmtMoney, StatusBadge, Table, td, tdStrong } from "./ui";

export function InvestmentsTable({ investments, action }: { investments: Investment[]; action?: (i: Investment) => React.ReactNode }) {
  return (
    <Table caption="Investment records" head={["Reference", "Service", "Date", "Amount", "Status", ...(action ? [""] : [])]}>
      {investments.map((i) => (
        <tr key={i.id}>
          <td className={tdStrong}>
            <span className="font-mono text-xs">{i.reference_number}</span>
            {i.summary && <span className="mt-1 block max-w-sm text-xs font-normal text-ink-muted [overflow-wrap:anywhere]">{i.summary}</span>}
          </td>
          <td className={td}>{i.division.name}</td>
          <td className={td + " whitespace-nowrap"}>{fmtDate(i.invested_on)}</td>
          <td className={td + " whitespace-nowrap tabular-nums text-ink"}>{fmtMoney(i.amount, i.currency)}</td>
          <td className={td}><StatusBadge status={i.status} /></td>
          {action && <td className={td + " text-right"}>{action(i)}</td>}
        </tr>
      ))}
    </Table>
  );
}
