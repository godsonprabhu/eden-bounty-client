import type { Metadata } from "next";
import { PageHero } from "@/components/site/PageHero";
import { SectionHeader, Shell } from "@/components/site/primitives";
import { ServiceCard } from "@/components/site/ServiceCard";
import { CtaBand } from "@/components/site/CtaBand";
import { businessDivisions } from "@/data/divisions";
import { divisionClusters } from "@/data/operations";

export const metadata: Metadata = {
  title: "Services",
  description: "EDEN BOUNTY Sdn. Bhd. organises its wholesale activities into commercial services.",
  alternates: { canonical: "/services" },
};

export default function ServicesPage() {
  return (
    <>
      <PageHero
        eyebrow="Services"
        title="Commercial services."
        intro="EDEN BOUNTY Sdn. Bhd. organises its wholesale activities into commercial services. Commercial terms are provided upon formal enquiry."
      >
        <div className="mt-12 flex flex-wrap gap-2">
          {divisionClusters.map((c) => (
            <span
              key={c.code}
              className="border border-line-strong px-3 py-1.5 font-mono text-[0.66rem] uppercase tracking-[0.18em] text-ink-muted"
            >
              {c.category}
            </span>
          ))}
        </div>
      </PageHero>

      <section className="eb-section border-b border-line" aria-labelledby="services-heading">
        <Shell>
          <div className="mb-12">
            <SectionHeader
              eyebrow="Commercial services"
              title="All commercial services."
              intro="Select any service to view full technical scope, commercial capabilities, and initiate a locked enquiry."
            />
          </div>
          <h2 id="services-heading" className="sr-only">
            All commercial services
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {businessDivisions.map((d, i) => (
              <ServiceCard key={d.id} service={d} index={i} />
            ))}
          </div>
        </Shell>
      </section>

      <CtaBand />
    </>
  );
}
