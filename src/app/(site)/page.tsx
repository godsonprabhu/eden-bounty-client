import Link from "next/link";
import { HomeHero } from "@/components/home/HomeHero";
import { ButtonLink, Reveal, SectionHeader, Shell } from "@/components/site/primitives";
import { ServiceCard } from "@/components/site/ServiceCard";
import { CtaBand } from "@/components/site/CtaBand";
import { siteConfig } from "@/config/site";
import { businessDivisions } from "@/data/divisions";
import { tradeWorkflow } from "@/data/operations";

export default function HomePage() {
  const featured = businessDivisions.filter((d) =>
    ["petroleum-products", "furnace-oil", "construction", "scrap-trading", "mineral-water", "agricultural-drones"].includes(d.id)
  );

  return (
    <>
      <HomeHero />

      {/* Company introduction */}
      <section className="eb-section relative border-b border-line">
        <Shell className="grid gap-14 lg:grid-cols-12">
          <Reveal className="lg:col-span-4">
            <p className="eb-eyebrow">The company</p>
          </Reveal>
          <div className="lg:col-span-8">
            <Reveal>
              <h2 className="eb-display text-[clamp(2rem,4.2vw,3.6rem)] text-ink">
                A Malaysian trading house organised into commercial services —{" "}
                <span className="text-ink-subtle">managed through clear terms and direct correspondence.</span>
              </h2>
            </Reveal>
            <div className="mt-14 grid gap-4 sm:grid-cols-3">
              {siteConfig.overview.pillars.map((p, i) => (
                <Reveal key={p.title} delay={i * 0.08} className="eb-glass eb-glass-hover p-7">
                  <h3 className="text-lg font-semibold text-ink">{p.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-ink-muted">{p.description}</p>
                </Reveal>
              ))}
            </div>
            <Reveal className="mt-10">
              <ButtonLink href="/about" variant="ghost">
                About Eden Bounty
              </ButtonLink>
            </Reveal>
          </div>
        </Shell>
      </section>

      {/* Services */}
      <section className="eb-section border-b border-line bg-paper-2">
        <Shell>
          <SectionHeader
            eyebrow="Services"
            align="split"
            title={
              <>
                Every service, <em className="text-brand">one</em> commercial desk.
              </>
            }
            intro={siteConfig.description}
          />
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((d, i) => (
              <ServiceCard key={d.id} service={d} index={i} />
            ))}
          </div>
          <Reveal className="mt-12 flex flex-wrap items-center justify-between gap-6 border-t border-line pt-8">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-ink-subtle">
              Centralized commercial desk for all 6 commercial services
            </p>
            <ButtonLink href="/services">All services</ButtonLink>
          </Reveal>
        </Shell>
      </section>

      {/* Operations teaser */}
      <section className="eb-section border-b border-line">
        <Shell>
          <SectionHeader
            eyebrow="How we work"
            align="split"
            title={
              <>
                From first enquiry to <em className="text-brand">documented</em> terms.
              </>
            }
            intro="Every trade follows the same disciplined course: scoped, reviewed, quoted under written terms, then coordinated through official correspondence."
          />
          <div className="mt-16 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {tradeWorkflow.map((s, i) => (
              <Reveal key={s.step} delay={i * 0.08} className="eb-glass eb-glass-hover group relative p-7">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-brand">STAGE {s.step}</span>
                    <span className="h-px w-10 bg-line-strong transition-all duration-500 group-hover:w-16 group-hover:bg-brand" aria-hidden="true" />
                  </div>
                  <h3 className="eb-display mt-10 text-3xl text-ink">{s.title}</h3>
                  <p className="mt-4 text-sm leading-relaxed text-ink-muted">{s.description}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal className="mt-10">
            <Link href="/rfq" className="font-mono text-xs uppercase tracking-[0.2em] text-ink underline decoration-brand underline-offset-8 hover:text-brand">
              Start an enquiry →
            </Link>
          </Reveal>
        </Shell>
      </section>

      <CtaBand />
    </>
  );
}
