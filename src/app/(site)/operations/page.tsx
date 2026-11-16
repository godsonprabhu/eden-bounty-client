import type { Metadata } from "next";
import Image from "next/image";
import { Globe, Layers, FileCheck } from "lucide-react";
import { PageHero } from "@/components/site/PageHero";
import { Reveal, SectionHeader, Shell } from "@/components/site/primitives";
import { CtaBand } from "@/components/site/CtaBand";
import { TradeChart } from "@/components/operations/TradeChart";
import { WorkflowStages } from "@/components/operations/WorkflowStages";
import { siteConfig } from "@/config/site";

export const metadata: Metadata = {
  title: "Operations",
  description: "Commercial sourcing and trade coordination across EDEN BOUNTY's business services.",
  alternates: { canonical: "/operations" },
};

const icons = { Globe, Layers, FileCheck } as const;

export default function OperationsPage() {
  return (
    <>
      <PageHero eyebrow="Operations" title="Sourcing and trade coordination." intro={siteConfig.supplyChain.description} />

      <section className="eb-section border-b border-line">
        <Shell>
          <SectionHeader
            eyebrow="Commercial network"
            align="split"
            title="One desk, four service clusters."
            intro="Every enquiry is routed from the Shah Alam head office to the relevant service cluster. Trade lanes are arranged per enquiry and confirmed in writing."
          />
          <Reveal className="mt-14">
            <TradeChart />
          </Reveal>
        </Shell>
      </section>

      <section className="eb-section border-b border-line bg-paper-2">
        <Shell>
          <SectionHeader eyebrow="Workflow" title="The course of every trade." className="mb-14" />
          <WorkflowStages />
        </Shell>
      </section>

      <section className="eb-section border-b border-line">
        <Shell className="grid items-center gap-14 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <SectionHeader eyebrow="Capabilities" title={siteConfig.supplyChain.title} />
            <div className="mt-10 divide-y divide-line border-y border-line">
              {siteConfig.supplyChain.capabilities.map((c, i) => {
                const Icon = icons[c.iconName as keyof typeof icons] ?? Globe;
                return (
                  <Reveal key={c.title} delay={i * 0.08} className="flex gap-6 py-6">
                    <Icon className="mt-1 h-5 w-5 shrink-0 text-brand" strokeWidth={1.4} aria-hidden="true" />
                    <div>
                      <h3 className="font-semibold text-ink">{c.title}</h3>
                      <p className="mt-1.5 text-sm text-ink-muted">{c.description}</p>
                    </div>
                  </Reveal>
                );
              })}
            </div>
          </div>
          <Reveal className="relative aspect-[4/5] overflow-hidden border border-line lg:col-span-6">
            <Image
              src="/images/capabilities/supply-chain.jpg"
              alt="Commercial logistics and supply chain"
              fill
              sizes="(min-width: 1024px) 50vw, 100vw"
              className="object-cover dark:brightness-[0.8]"
            />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,transparent_55%,rgb(var(--eb-scrim)/0.8))]" aria-hidden="true" />
            <p className="absolute bottom-6 left-6 right-6 font-mono text-[0.66rem] uppercase tracking-[0.2em] text-white/90">
              All commercial quotations are executed through formal, documented terms
            </p>
          </Reveal>
        </Shell>
      </section>

      <CtaBand />
    </>
  );
}
