import type { Metadata } from "next";
import { PageHero } from "@/components/site/PageHero";
import { Reveal, SectionHeader, Shell } from "@/components/site/primitives";
import { CtaBand } from "@/components/site/CtaBand";
import { siteConfig } from "@/config/site";

export const metadata: Metadata = {
  title: "About",
  description:
    "EDEN BOUNTY Sdn. Bhd. is an incorporated Malaysian private limited company based in Shah Alam, Selangor, operating across commercial wholesale services.",
  alternates: { canonical: "/about" },
};

// Mission & vision are written from the company's published positioning; confirm final wording with management.
const mission =
  "To conduct wholesale trade across our commercial services with accurate business information, formal quotations and transaction terms agreed in writing before any trade proceeds.";
const vision =
  "To be a dependable Malaysian commercial counterparty — recognised for transparent representation, professional correspondence and disciplined trade practice.";

const values = [
  { title: "Transparent representation", body: "Clear commercial scope across our commercial services, presented without overstatement." },
  { title: "Factual information", body: "A focus on accurate business information and trading parameters in every exchange." },
  { title: "Documented terms", body: "Transaction terms are discussed and mutually agreed before proceeding." },
  { title: "Direct correspondence", body: "Commercial enquiries are handled directly through the official business email." },
];

export default function AboutPage() {
  return (
    <>
      <PageHero
        eyebrow="About"
        title="A trading house built on clear terms."
        intro="EDEN BOUNTY Sdn. Bhd. is an incorporated Malaysian private limited company based in Shah Alam, Selangor, operating across commercial wholesale services."
      />

      <section id="overview" className="eb-section scroll-mt-24 border-b border-line bg-paper-2">
        <Shell>
          <SectionHeader eyebrow="Company overview" title={siteConfig.overview.headline} intro={siteConfig.overview.summary} align="split" />
          <div className="mt-14 grid gap-4 sm:grid-cols-3">
            {siteConfig.overview.pillars.map((p, i) => (
              <Reveal key={p.title} delay={i * 0.07} className="eb-glass p-7">
                <h3 className="mt-8 text-lg font-semibold text-ink">{p.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-muted">{p.description}</p>
              </Reveal>
            ))}
          </div>
        </Shell>
      </section>

      <section id="vision-mission" className="eb-section scroll-mt-24 border-b border-line">
        <Shell className="grid gap-12 lg:grid-cols-2">
          {[
            ["Mission", mission],
            ["Vision", vision],
          ].map(([k, v], i) => (
            <Reveal key={k} delay={i * 0.1} className="eb-frame p-8 sm:p-12">
              <p className="eb-eyebrow">{k}</p>
              <p className="eb-display mt-8 text-[clamp(1.8rem,3vw,2.6rem)] text-ink">{v}</p>
            </Reveal>
          ))}
        </Shell>
      </section>

      <section className="eb-section border-b border-line bg-paper-2">
        <Shell>
          <SectionHeader eyebrow="Values" title="How we conduct business." intro={siteConfig.compliance.description} align="split" />
          <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {values.map((v, i) => (
              <Reveal key={v.title} delay={i * 0.07} className="eb-glass eb-glass-hover p-7">
                <h3 className="eb-display mt-10 text-[1.75rem] text-ink">{v.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-muted">{v.body}</p>
              </Reveal>
            ))}
          </div>
        </Shell>
      </section>

      <section id="leadership" className="eb-section scroll-mt-24 border-b border-line">
        <Shell className="grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <SectionHeader eyebrow="Management / Leadership" title="Directed from one commercial desk." />
          </div>
          <Reveal className="space-y-5 text-ink-muted lg:col-span-7">
            <p>
              {siteConfig.legalName} is a privately held Malaysian company. Its commercial divisions are directed centrally from the head
              office in Shah Alam, Selangor, and every enquiry is reviewed and answered through a single commercial desk.
            </p>
            <p className="text-sm">
              Details of the company&rsquo;s directors and officers are provided to counterparties on written request to{" "}
              <a href={`mailto:${siteConfig.contact.email}`} className="text-ink underline decoration-brand underline-offset-4 hover:text-brand">
                {siteConfig.contact.email}
              </a>
              .
            </p>
          </Reveal>
        </Shell>
      </section>

      <section id="structure" className="eb-section scroll-mt-24 border-b border-line bg-paper-2">
        <span id="governance" className="sr-only" aria-hidden="true" />
        <Shell className="grid gap-14 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <SectionHeader eyebrow="Company structure" title={siteConfig.compliance.title} />
            <Reveal className="mt-8">
              <p className="text-ink-muted">{siteConfig.compliance.statement}</p>
            </Reveal>
          </div>
          <div className="space-y-8 lg:col-span-7">
            <Reveal className="eb-frame p-8">
              <p className="eb-eyebrow">Corporate record</p>
              <dl className="mt-6 divide-y divide-line">
                {[
                  ["Legal name", siteConfig.legalName],
                  ["Registration (SSM)", siteConfig.contact.registrationNumber ?? "—"],
                  ["Registered address", siteConfig.contact.address ?? "—"],
                  ["Country", siteConfig.country],
                  ["Official email", siteConfig.contact.email],
                ].map(([k, v]) => (
                  <div key={k} className="grid gap-1 py-4 sm:grid-cols-3 sm:gap-6">
                    <dt className="font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-subtle">{k}</dt>
                    <dd className="text-sm text-ink sm:col-span-2 [overflow-wrap:anywhere]">{v}</dd>
                  </div>
                ))}
              </dl>
            </Reveal>
            <Reveal>
              <p className="eb-eyebrow">Commercial standards</p>
              <ul className="mt-5 space-y-3">
                {siteConfig.compliance.notes.map((n) => (
                  <li key={n} className="flex gap-4 border-b border-line pb-3 text-sm text-ink-muted">
                    <span className="mt-2.5 h-px w-4 shrink-0 bg-brand" aria-hidden="true" />
                    {n}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </Shell>
      </section>

      <CtaBand />
    </>
  );
}
