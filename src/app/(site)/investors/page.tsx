import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, Mail, MessageSquareText } from "lucide-react";
import { PageHero } from "@/components/site/PageHero";
import { ButtonLink, Reveal, SectionHeader, Shell } from "@/components/site/primitives";
import { ServiceCard } from "@/components/site/ServiceCard";
import { Glass } from "@/components/ui/Glass";
import { siteConfig } from "@/config/site";
import { businessDivisions } from "@/data/divisions";

export const metadata: Metadata = {
  title: "Investors",
  description:
    "Corporate information for EDEN BOUNTY Sdn. Bhd., a Malaysian private limited company in wholesale trading and business solutions.",
  alternates: { canonical: "/investors" },
};

const investorMailto = `mailto:${siteConfig.contact.email}?subject=${encodeURIComponent("Investor correspondence — EDEN BOUNTY Sdn. Bhd.")}`;

// Client-verified corporate facts only. No financial, shareholding or offering data is published.
const identity: Array<[string, string]> = [
  ["Legal entity", siteConfig.legalName],
  ["Registration number", siteConfig.contact.registrationNumber ?? "—"],
  ["Company type", "Malaysian private limited company (Sdn. Bhd.)"],
  ["Registered address", siteConfig.contact.address ?? "—"],
  ["Business focus", "Wholesale trading and business solutions"],
  ["Commercial scope", "Commercial trading services"],
  ["Official email", siteConfig.contact.email],
];

const keyFacts: Array<[string, string]> = [
  ["Entity type", "Sdn. Bhd. (private limited)"],
  ["SSM registration", "202501058702"],
  ["Head office", "Shah Alam, Selangor"],
  ["Business focus", "Wholesale trading"],
];

const sections = [
  ["identity", "Corporate identity"],
  ["overview", "Business overview"],
  ["services", "Services"],
  ["governance", "Governance"],
  ["correspondence", "Correspondence"],
];

const overview = [
  {
    title: "Business model",
    body: "A wholesale trading and business solutions company. Activities are organised into commercial services, each handled through a single commercial desk.",
  },
  {
    title: "Commercial activities",
    body: "Trading across energy and hydrocarbons, industrial materials, consumer goods, construction / building promotion, and drone solutions, as listed below.",
  },
  {
    title: "Business approach",
    body: "Each enquiry is scoped and reviewed, then quoted in writing. Terms are agreed with the counterparty before any trade proceeds.",
  },
];

export default function InvestorsPage() {
  return (
    <>
      <PageHero
        eyebrow="Investor relations"
        title="Corporate information, stated plainly."
        intro="This page sets out confirmed corporate facts about EDEN BOUNTY Sdn. Bhd. for prospective partners, counterparties and other stakeholders. For anything not shown here, please write to us."
      >
        <dl className="mt-12 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {keyFacts.map(([k, v]) => (
            <Glass key={k} className="p-5">
              <dt className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-subtle">{k}</dt>
              <dd className="mt-2 text-sm font-semibold text-ink sm:text-base">{v}</dd>
            </Glass>
          ))}
        </dl>
      </PageHero>

      {/* Section index */}
      <nav aria-label="Investor relations sections" className="eb-nav-glass sticky top-[72px] z-30">
        <Shell>
          <ul className="flex gap-1 overflow-x-auto py-2 [scrollbar-width:none]">
            {sections.map(([id, label]) => (
              <li key={id} className="shrink-0">
                <a
                  href={`#${id}`}
                  className="flex min-h-11 items-center gap-2 px-3 font-mono text-[0.66rem] uppercase tracking-[0.18em] text-ink-muted transition-colors hover:text-brand"
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </Shell>
      </nav>

      {/* Corporate identity */}
      <section id="identity" className="eb-section scroll-mt-32 border-b border-line">
        <Shell className="grid gap-14 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <SectionHeader eyebrow="Corporate identity" title="The registered entity." />
            <Reveal className="mt-8">
              <p className="text-ink-muted">
                {siteConfig.legalName} is incorporated in Malaysia as a private limited company and is based in Shah Alam, Selangor.
              </p>
            </Reveal>
          </div>
          <Reveal className="eb-frame p-7 sm:p-10 lg:col-span-7" delay={0.08}>
            <p className="eb-eyebrow">Corporate record</p>
            <dl className="mt-6 divide-y divide-line">
              {identity.map(([k, v]) => (
                <div key={k} className="grid gap-1 py-4 sm:grid-cols-3 sm:gap-6">
                  <dt className="font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-subtle">{k}</dt>
                  <dd className="text-sm text-ink sm:col-span-2 [overflow-wrap:anywhere]">{v}</dd>
                </div>
              ))}
            </dl>
          </Reveal>
        </Shell>
      </section>

      {/* Business overview */}
      <section id="overview" className="eb-section scroll-mt-32 border-b border-line bg-paper-2">
        <Shell>
          <SectionHeader
            eyebrow="Business overview"
            align="split"
            title={
              <>
                A wholesale trading house, <em className="text-brand">organised</em> by service.
              </>
            }
            intro={siteConfig.compliance.description}
          />
          <div className="mt-16 grid gap-6 md:grid-cols-3">
            {overview.map((o, i) => (
              <Reveal key={o.title} delay={i * 0.08} className="eb-glass eb-glass-hover p-8">
                <h3 className="eb-display text-[2rem] text-ink">{o.title}</h3>
                <p className="mt-4 text-sm leading-relaxed text-ink-muted">{o.body}</p>
              </Reveal>
            ))}
          </div>
        </Shell>
      </section>

      {/* Commercial services */}
      <section id="services" className="eb-section scroll-mt-32 border-b border-line">
        <Shell>
          <SectionHeader
            eyebrow="Commercial services"
            align="split"
            title="Our services."
            intro="These are the same services shown on the Services page. Commercial terms for each are provided on formal enquiry."
          />
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {businessDivisions.map((d, i) => (
              <ServiceCard key={d.id} service={d} index={i} />
            ))}
          </div>
          <Reveal className="mt-10">
            <Link href="/services" className="font-mono text-xs uppercase tracking-[0.2em] text-ink underline decoration-brand underline-offset-8 hover:text-brand">
              Service details on the Services page →
            </Link>
          </Reveal>
        </Shell>
      </section>

      {/* Governance & transparency */}
      <section id="governance" className="eb-section scroll-mt-32 border-b border-line bg-paper-2">
        <Shell className="grid gap-14 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <SectionHeader eyebrow="Governance & transparency" title="Responsible operations." />
            <Reveal className="mt-8 space-y-5 text-ink-muted">
              <p>{siteConfig.compliance.statement}</p>
              <p>Commercial confidentiality is maintained for all business enquiries and trade correspondence.</p>
            </Reveal>
          </div>
          <div className="space-y-6 lg:col-span-7">
            <Reveal className="eb-glass p-7 sm:p-9">
              <p className="eb-eyebrow">Commercial standards</p>
              <ul className="mt-6 space-y-4">
                {siteConfig.compliance.notes.map((n) => (
                  <li key={n} className="flex gap-4 text-sm text-ink-muted">
                    <span className="mt-2.5 h-px w-4 shrink-0 bg-brand" aria-hidden="true" />
                    {n}
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal id="investment-information" className="eb-frame scroll-mt-32 p-7 sm:p-9" delay={0.06}>
              <p className="eb-eyebrow">Investment information</p>
              <p className="mt-5 text-sm leading-relaxed text-ink-muted">
                {siteConfig.legalName} is a private limited company. Its shares are not publicly listed, and no shares or investment
                products are offered through this website. Financial statements, shareholding information and other corporate documents
                are not published here. Requests for such information should be made in writing to the official company email.
              </p>
            </Reveal>
          </div>
        </Shell>
      </section>

      {/* Investor correspondence */}
      <section id="correspondence" className="eb-section scroll-mt-32">
        <Shell>
          <SectionHeader eyebrow="Correspondence" title="Write to the right desk." />
          <div className="mt-14 grid gap-6 md:grid-cols-2">
            <Reveal className="eb-frame flex flex-col p-8 sm:p-10">
              <Mail className="h-5 w-5 text-brand" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="eb-display mt-8 text-[2.2rem] text-ink">Investor correspondence</h3>
              <p className="mt-4 text-sm leading-relaxed text-ink-muted">
                For corporate, partnership or stakeholder questions, email the company directly with
                &ldquo;Investor correspondence&rdquo; in the subject line.
              </p>
              <div className="mt-auto pt-10">
                <ButtonLink href={investorMailto}>Email {siteConfig.contact.email}</ButtonLink>
              </div>
            </Reveal>
            <Reveal className="eb-glass flex flex-col p-8 sm:p-10" delay={0.08}>
              <MessageSquareText className="h-5 w-5 text-brand" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="eb-display mt-8 text-[2.2rem] text-ink">General commercial enquiries</h3>
              <p className="mt-4 text-sm leading-relaxed text-ink-muted">
                To buy, supply or trade with a service, use the enquiry desk. It sends your RFQ to the right service.
              </p>
              <div className="mt-auto pt-10">
                <Link
                  href="/rfq"
                  className="group inline-flex min-h-12 items-center gap-3 border border-line-strong px-6 text-[0.78rem] font-semibold uppercase tracking-[0.16em] text-ink transition-colors hover:border-brand hover:text-brand"
                >
                  Open the enquiry desk
                  <ArrowUpRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" />
                </Link>
              </div>
            </Reveal>
          </div>
        </Shell>
      </section>
    </>
  );
}
