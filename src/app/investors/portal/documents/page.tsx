"use client";

import { Download, FileText } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { Empty, fmtBytes, fmtDate, humanize, PageHeader, Panel, Resource, Table, td, tdStrong, useResource } from "@/components/portal/ui";
import type { InvestorDocument } from "@/types/portal";

export default function InvestorDocumentsPage() {
  const documents = useResource<InvestorDocument[]>("/investor/documents");
  return (
    <>
      <PageHeader
        eyebrow="Documents"
        title="Reports and documents"
        intro="Financial reports and investment documents the company has issued to you. Downloads require your signed-in session; the files are not available through public links."
      />
      <Panel>
        <Resource state={documents} isEmpty={(d) => d.length === 0} empty={<Empty title="No documents have been issued yet">Documents appear here once the company publishes them to your account.</Empty>}>
          {(rows) => (
            <Table caption="Your documents" head={["Document", "Type", "Issued", "Size", ""]}>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td className={tdStrong}>
                    <span className="flex items-start gap-2">
                      <FileText className="mt-0.5 h-4 w-4 shrink-0 text-brand" strokeWidth={1.5} aria-hidden="true" />
                      <span className="[overflow-wrap:anywhere]">{d.title}</span>
                    </span>
                  </td>
                  <td className={td}>{humanize(d.category)}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtDate(d.published_at ?? d.created_at)}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtBytes(d.size_bytes)}</td>
                  <td className={td + " text-right"}>
                    <a
                      href={apiUrl(`/investor/documents/${d.id}/download`)}
                      className="inline-flex min-h-9 items-center gap-2 border border-line-strong px-3 font-mono text-[0.66rem] uppercase tracking-[0.14em] text-ink hover:border-brand hover:text-brand"
                    >
                      <Download className="h-3.5 w-3.5" aria-hidden="true" /> Download<span className="sr-only"> {d.title}</span>
                    </a>
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Resource>
      </Panel>
    </>
  );
}
