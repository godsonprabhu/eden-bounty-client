"use client";

import { useState } from "react";
import { Mail, MapPin, Clock } from "lucide-react";
import { TradeEnquiryForm, type TradeEnquiryFormState } from "@/components/forms/TradeEnquiryForm";
import { siteConfig } from "@/config/site";
import { divisionClusters } from "@/data/operations";
import { cn } from "@/lib/utils";
import { Reveal } from "@/components/site/primitives";

export function ContactDesk({ initialDivisionId }: { initialDivisionId?: string }) {
  const [divisionId, setDivisionId] = useState<string | undefined>(initialDivisionId);
  const [live, setLive] = useState<TradeEnquiryFormState | null>(null);

  const pick = (id: string) => {
    setDivisionId(id);
    document.getElementById("inquiry-console")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const summary: Array<[string, string]> = [
    ["Stage", `0${live?.currentStage || 1} of 04`],
    ["Service", live?.selectedDivision ? live.selectedDivision.name : "Not selected"],
    ["Company", live?.formData.companyName || "—"],
    ["Contact", live?.formData.fullName || "—"],
    ["Product focus", live?.formData.productFocus || "—"],
  ];

  return (
    <div className="grid gap-10 lg:grid-cols-12">
      <div id="inquiry-console" className="min-w-0 scroll-mt-28 lg:col-span-7">
        <TradeEnquiryForm key={divisionId ?? "none"} initialDivisionId={divisionId} onStateChange={setLive} />
      </div>

      <aside className="min-w-0 space-y-6 lg:col-span-5">
        <Reveal className="eb-frame p-7">
          <p className="eb-eyebrow">Quick routing</p>
          <div className="mt-5 grid gap-2">
            {divisionClusters.map((c) => {
              const active = c.defaultDivisionId === divisionId;
              return (
                <button
                  key={c.code}
                  type="button"
                  onClick={() => pick(c.defaultDivisionId)}
                  aria-pressed={active}
                  className={cn(
                    "group flex min-h-14 cursor-pointer items-center justify-between gap-4 border px-4 py-3 text-left transition-colors duration-300",
                    active ? "border-brand bg-brand-soft" : "border-line hover:border-line-strong hover:bg-panel-2"
                  )}
                >
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-ink">{c.category}</span>
                    <span className="mt-0.5 block truncate text-xs text-ink-subtle">{c.sectors.join(" · ")}</span>
                  </span>
                  <span className="font-mono text-[0.6rem] tracking-[0.16em] text-brand">{c.code.replace("EB-SECTOR-", "S")}</span>
                </button>
              );
            })}
          </div>
        </Reveal>

        <Reveal className="eb-frame p-7" delay={0.05}>
          <p className="eb-eyebrow">Enquiry summary</p>
          <dl className="mt-5 divide-y divide-line">
            {summary.map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-6 py-3">
                <dt className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-ink-subtle">{k}</dt>
                <dd className="min-w-0 truncate text-right text-sm text-ink" title={v}>
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </Reveal>

        <Reveal className="eb-frame p-7" delay={0.1}>
          <p className="eb-eyebrow">Official contact</p>
          <p className="eb-display mt-5 text-3xl text-ink">{siteConfig.legalName}</p>
          <ul className="mt-6 space-y-4 text-sm text-ink-muted">
            <li className="flex gap-3">
              <Mail className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
              <a href={`mailto:${siteConfig.contact.email}`} className="text-ink underline decoration-line-strong underline-offset-4 hover:decoration-brand">
                {siteConfig.contact.email}
              </a>
            </li>
            <li className="flex gap-3">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
              <address className="not-italic">{siteConfig.contact.address}</address>
            </li>
            <li className="flex gap-3">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
              Shah Alam, Selangor · UTC+8
            </li>
          </ul>
          <p className="mt-6 border-t border-line pt-5 text-xs text-ink-subtle">
            Commercial quotations upon request, subject to review. Transaction terms are discussed and mutually agreed before proceeding.
          </p>
        </Reveal>
      </aside>
    </div>
  );
}
