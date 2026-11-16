import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
  Cpu,
  Boxes,
  ClipboardList,
  Package,
  Users,
  Info,
  Layers,
  Sparkles,
} from "lucide-react";
import { Reveal, Shell } from "@/components/site/primitives";
import { ServiceImageSlider } from "@/components/site/ServiceImageSlider";
import { TradeEnquiryForm } from "@/components/forms/TradeEnquiryForm";
import { businessDivisions } from "@/data/divisions";
import { siteConfig } from "@/config/site";

interface ServicePageProps {
  params: Promise<{ slug: string }>;
}

export function generateStaticParams() {
  return businessDivisions.filter((d) => d.active !== false).map((d) => ({ slug: d.id }));
}

export async function generateMetadata({ params }: ServicePageProps): Promise<Metadata> {
  const { slug } = await params;
  const service = businessDivisions.find((d) => d.id === slug && d.active !== false);
  if (!service) return { title: "Service Not Found" };

  return {
    title: `${service.name} — Commercial Services`,
    description: service.description,
    alternates: { canonical: `/services/${service.id}` },
  };
}

export default async function ServiceDetailPage({ params }: ServicePageProps) {
  const { slug } = await params;
  const service = businessDivisions.find((d) => d.id === slug && d.active !== false);

  if (!service) {
    notFound();
  }

  const isAgriTech = service.id === "agricultural-drones";
  const capabilities = service.capabilities ?? service.highlights ?? [];
  const specifications = service.specifications ?? [];
  const applications = service.applications ?? [];
  const productOfferings = service.productOfferings ?? [];
  const packagingOptions = service.packagingOptions ?? [];
  const targetCustomers = service.targetCustomers ?? [];
  const subcategories = service.subcategories ?? [];

  return (
    <>
      {/* 1. Breadcrumb & Service Detail Hero */}
      <section className="relative border-b border-line bg-paper pt-28 pb-14 sm:pt-36 sm:pb-18">
        <Shell>
          <nav aria-label="Breadcrumb" className="mb-6">
            <ol className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-ink-muted">
              <li>
                <Link href="/" className="transition-colors hover:text-brand">
                  Home
                </Link>
              </li>
              <li className="text-line-strong">/</li>
              <li>
                <Link href="/services" className="transition-colors hover:text-brand">
                  Services
                </Link>
              </li>
              <li className="text-line-strong">/</li>
              <li className="text-brand font-semibold" aria-current="page">
                {service.name}
              </li>
            </ol>
          </nav>

          <div className="grid gap-10 lg:grid-cols-12 lg:items-end">
            <div className="lg:col-span-8">
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <span className="rounded-[2px] bg-brand-soft border border-brand/40 px-3 py-1 font-mono text-[0.72rem] uppercase tracking-wider text-brand font-semibold">
                  {service.sector || "Commercial Service"}
                </span>
              </div>
              <h1 className="eb-display text-[clamp(2.5rem,5.5vw,4.5rem)] font-bold text-ink leading-tight">
                {service.name}
              </h1>
              <p className="mt-5 max-w-2xl text-base sm:text-lg leading-relaxed text-ink-muted">
                {service.description}
              </p>
            </div>

            <div className="lg:col-span-4 flex flex-col justify-end">
              <div className="eb-glass rounded-[2px] border border-line p-5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-ink-subtle block mb-1">
                  Central Trade Desk
                </span>
                <p className="text-xs text-ink-muted leading-relaxed">
                  Managed centrally through {siteConfig.legalName} in Shah Alam, Selangor.
                </p>
                <a
                  href="#service-enquiry"
                  className="mt-4 inline-flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-wider text-brand hover:underline"
                >
                  <span>Request Quotation for this Service ↓</span>
                </a>
              </div>
            </div>
          </div>
        </Shell>
      </section>

      {/* Main Service Content Grid */}
      <section className="eb-section border-b border-line bg-paper-2">
        <Shell className="grid gap-12 lg:grid-cols-12">
          {/* Left Column: Visual Showcase, Scope, Subcategories, Specs, Advisories */}
          <div className="lg:col-span-7 space-y-8">
            {/* Large Relevant Service Image */}
            <Reveal className="group relative aspect-[16/10] overflow-hidden rounded-[2px] border border-line bg-panel shadow-sm">
              <ServiceImageSlider
                images={service.images}
                fallbackImage={service.image}
                alt={`${service.name} — EDEN BOUNTY commercial service`}
                priority={true}
                sizes="(min-width: 1024px) 60vw, 100vw"
              />
              <div
                className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent pointer-events-none"
                aria-hidden="true"
              />
              <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-white/90 font-mono text-[0.68rem] uppercase tracking-wider pointer-events-none">
                <span>{service.name}</span>
                <span>{service.sector || "Commercial Service"}</span>
              </div>
            </Reveal>

            {/* Scope of Services */}
            <div className="eb-glass rounded-[2px] border border-line p-6 sm:p-8 space-y-4">
              <div className="flex items-center gap-2.5">
                <ClipboardList className="h-5 w-5 text-brand" />
                <h2 className="eb-display text-xl sm:text-2xl font-bold text-ink">
                  Scope of Services
                </h2>
              </div>
              <p className="text-sm leading-relaxed text-ink-muted">
                {service.scopeFocus}
              </p>
              <div className="flex items-center gap-3 pt-3 border-t border-line text-xs font-mono text-ink-subtle">
                <ShieldCheck className="h-4 w-4 text-brand shrink-0" />
                <span>Verified commercial documentation · Official Malaysian entity terms</span>
              </div>
            </div>

            {/* Product Types / Service Offerings (when present) */}
            {productOfferings.length > 0 && (
              <div className="eb-glass rounded-[2px] border border-line p-6 sm:p-8 space-y-5">
                <div className="flex items-center gap-2.5">
                  <Sparkles className="h-5 w-5 text-brand" />
                  <h3 className="eb-display text-xl sm:text-2xl font-bold text-ink">
                    Product Types & Offerings
                  </h3>
                </div>
                <p className="text-xs text-ink-muted leading-relaxed">
                  Available commercial product grades and specialized service options provided by {siteConfig.legalName}.
                </p>
                <div className="grid gap-3 sm:grid-cols-2 pt-2">
                  {productOfferings.map((offering) => (
                    <div
                      key={offering}
                      className="flex items-center gap-3 rounded-[2px] border border-line bg-paper/60 p-3 text-xs text-ink"
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-brand shrink-0" />
                      <span className="font-medium">{offering}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Subcategories (Detailed Breakdown: e.g. Ferrous/Non-Ferrous, Agri/Surveillance Drones) */}
            {subcategories.length > 0 && (
              <div className="space-y-6">
                <div className="flex items-center gap-2.5">
                  <Layers className="h-5 w-5 text-brand" />
                  <h3 className="eb-display text-xl sm:text-2xl font-bold text-ink">
                    Classification & Portfolio Breakdown
                  </h3>
                </div>

                <div className="space-y-6">
                  {subcategories.map((sub) => (
                    <div
                      key={sub.title}
                      className="eb-frame rounded-[2px] p-6 sm:p-7 space-y-4"
                    >
                      <div className="border-b border-line pb-3">
                        <span className="eb-eyebrow">Category</span>
                        <h4 className="eb-display text-lg sm:text-xl font-bold text-ink mt-1">
                          {sub.title}
                        </h4>
                        {sub.description && (
                          <p className="mt-1 text-xs text-ink-muted leading-relaxed">
                            {sub.description}
                          </p>
                        )}
                      </div>

                      {/* Items */}
                      {sub.items && sub.items.length > 0 && (
                        <div className="space-y-2">
                          <span className="font-mono text-[0.68rem] uppercase tracking-wider text-ink-subtle">
                            Commercial Materials & Capabilities
                          </span>
                          <ul className="grid gap-2 sm:grid-cols-2">
                            {sub.items.map((item) => (
                              <li
                                key={item}
                                className="flex items-center gap-2.5 text-xs text-ink-muted"
                              >
                                <CheckCircle2 className="h-3.5 w-3.5 text-brand shrink-0" />
                                <span>{item}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Sub-specs if present (e.g. Drone capabilities) */}
                      {sub.specs && sub.specs.length > 0 && (
                        <div className="pt-3 border-t border-line space-y-2">
                          <span className="font-mono text-[0.68rem] uppercase tracking-wider text-ink-subtle">
                            Operational Parameters
                          </span>
                          <div className="divide-y divide-line border-y border-line">
                            {sub.specs.map((spec) => (
                              <div
                                key={spec.label}
                                className="py-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs"
                              >
                                <span className="font-mono text-[0.7rem] uppercase tracking-wider text-ink-subtle">
                                  {spec.label}
                                </span>
                                <span className="font-semibold text-ink sm:text-right">
                                  {spec.value}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Operational Benefits if present */}
                      {sub.benefits && sub.benefits.length > 0 && (
                        <div className="pt-3 border-t border-line space-y-2">
                          <span className="font-mono text-[0.68rem] uppercase tracking-wider text-ink-subtle">
                            Operational Advantages
                          </span>
                          <ul className="space-y-1.5">
                            {sub.benefits.map((benefit) => (
                              <li
                                key={benefit}
                                className="flex items-start gap-2 text-xs text-ink-muted"
                              >
                                <span className="text-brand font-bold mt-0.5">•</span>
                                <span>{benefit}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Technical Specifications */}
            {specifications.length > 0 && (
              <div className="eb-glass rounded-[2px] border border-line p-6 sm:p-8 space-y-5">
                <div className="flex items-center gap-2.5">
                  <Cpu className="h-5 w-5 text-brand" />
                  <h3 className="eb-display text-xl sm:text-2xl font-bold text-ink">
                    Technical Specifications
                  </h3>
                </div>
                <p className="text-xs text-ink-muted leading-relaxed">
                  Commercial parameters and typical technical tolerances governing {service.name}. Parameters represent indicative commercial specifications subject to batch analysis or contract certificate.
                </p>
                <div className="divide-y divide-line border-y border-line">
                  {specifications.map((spec) => (
                    <div
                      key={spec.label}
                      className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs"
                    >
                      <span className="font-mono uppercase tracking-wider text-ink-subtle">
                        {spec.label}
                      </span>
                      <span className="font-heading font-semibold text-ink sm:text-right">
                        {spec.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Furnace Oil Handling Advisory */}
            {service.handlingNotes && (
              <div className="rounded-[2px] border border-amber-500/30 bg-amber-500/10 p-5 space-y-2">
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-mono text-xs font-semibold uppercase tracking-wider">
                  <Info className="h-4 w-4" />
                  <span>Handling & Storage Advisory</span>
                </div>
                <p className="text-xs text-ink-muted leading-relaxed">
                  {service.handlingNotes}
                </p>
              </div>
            )}

            {/* Drone Specific Statutory Regulatory Notice */}
            {isAgriTech && (
              <div className="rounded-[2px] border border-brand/30 bg-brand-soft/40 p-5 space-y-3 font-mono text-xs text-ink-muted leading-relaxed">
                <div className="flex items-center gap-2 text-brand font-bold uppercase tracking-wider">
                  <ShieldCheck className="h-4 w-4" />
                  <span>STATUTORY REGULATORY NOTICE</span>
                </div>
                <p>
                  EDEN BOUNTY does not manufacture drones, claim official partnership or authorized dealership without written confirmation, own or operate an aircraft fleet, or provide flight or spraying services.
                </p>
                <p className="text-[11px] text-ink-subtle">
                  Notice: Any manufacturer authorisation or distributorship relationship is subject to direct written confirmation.
                </p>
              </div>
            )}
          </div>

          {/* Right Column: Packaging, Target Customers, Applications, Capabilities, Process */}
          <div className="lg:col-span-5 space-y-6">
            {/* Packaging & Supply Options (when provided) */}
            {packagingOptions.length > 0 && (
              <div className="eb-frame rounded-[2px] p-6 sm:p-8 space-y-4">
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4 text-brand" />
                  <span className="eb-eyebrow">Logistics & Supply</span>
                </div>
                <h3 className="eb-display text-xl font-bold text-ink">
                  Packaging & Supply Options
                </h3>
                <p className="text-xs text-ink-muted">
                  Standard packaging formats and commercial dispatch modes available for wholesale order.
                </p>
                <ul className="space-y-2.5 pt-2">
                  {packagingOptions.map((opt) => (
                    <li key={opt} className="flex items-start gap-2.5 text-xs text-ink-muted">
                      <span className="font-mono text-brand font-bold mt-0.5">•</span>
                      <span>{opt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Target Customers & Industries (when provided) */}
            {targetCustomers.length > 0 && (
              <div className="eb-glass rounded-[2px] border border-line p-6 sm:p-8 space-y-4">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-brand" />
                  <span className="eb-eyebrow">Client Base</span>
                </div>
                <h3 className="eb-display text-xl font-bold text-ink">
                  Target Customers & Industries
                </h3>
                <ul className="space-y-2.5 pt-2">
                  {targetCustomers.map((cust) => (
                    <li key={cust} className="flex items-center gap-2.5 text-xs text-ink-muted">
                      <CheckCircle2 className="h-3.5 w-3.5 text-brand shrink-0" />
                      <span>{cust}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Applications & Use Cases */}
            {applications.length > 0 && (
              <div className="eb-glass rounded-[2px] border border-line p-6 sm:p-8 space-y-4">
                <div className="flex items-center gap-2">
                  <Boxes className="h-4 w-4 text-brand" />
                  <span className="eb-eyebrow">Industry Sectors</span>
                </div>
                <h3 className="eb-display text-xl font-bold text-ink">
                  Applications & Use Cases
                </h3>
                <ul className="space-y-3 pt-2">
                  {applications.map((app) => (
                    <li key={app} className="flex items-start gap-3 text-xs text-ink-muted">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                      <span>{app}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Features and Capabilities */}
            {capabilities.length > 0 && (
              <div className="eb-frame rounded-[2px] p-6 sm:p-8 space-y-4">
                <span className="eb-eyebrow">Service Capabilities</span>
                <h3 className="eb-display text-xl font-bold text-ink">
                  Features & Capabilities
                </h3>
                <ul className="mt-4 space-y-3">
                  {capabilities.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-xs text-ink-muted">
                      <CheckCircle2 className="h-4 w-4 text-brand shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Transaction Protocol */}
            <div className="eb-glass rounded-[2px] border border-line p-6 sm:p-8 space-y-4">
              <span className="eb-eyebrow">Trade Protocol</span>
              <h3 className="eb-display text-xl font-bold text-ink">
                Commercial Process
              </h3>
              <ul className="space-y-3 text-xs text-ink-muted">
                <li className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                  <span>Direct formal submission via the service enquiry form below.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                  <span>Scope review by our commercial operations desk in Shah Alam.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                  <span>Written quotation and verified commercial terms agreed prior to execution.</span>
                </li>
              </ul>
            </div>
          </div>
        </Shell>
      </section>

      {/* Service-Specific Enquiry Form */}
      <section id="service-enquiry" className="eb-section border-b border-line bg-paper scroll-mt-20">
        <Shell>
          <div className="mb-10 max-w-3xl">
            <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-brand mb-3">
              <span>Dedicated Enquiry Desk</span>
            </div>
            <h2 className="eb-display text-[clamp(2.2rem,4.5vw,3.8rem)] font-bold text-ink leading-tight">
              Enquire about {service.name}.
            </h2>
            <p className="mt-4 text-base sm:text-lg text-ink-muted leading-relaxed">
              Submit your Request for Quotation directly to the {service.name} commercial desk.
              Your service selection is pre-locked to guarantee rapid, targeted review.
            </p>
          </div>

          <div className="mt-8 rounded-[2px] border border-line bg-panel p-6 sm:p-10 shadow-lg">
            <TradeEnquiryForm
              initialDivisionId={service.id}
              lockDivision={true}
            />
          </div>

          <div className="mt-8 flex items-center justify-between text-xs text-ink-subtle">
            <Link
              href="/services"
              className="group inline-flex items-center gap-2 font-mono uppercase tracking-[0.18em] text-ink-muted hover:text-brand transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-1" />
              <span>Back to all services</span>
            </Link>
            <Link
              href="/rfq"
              className="inline-flex items-center gap-1.5 font-mono uppercase tracking-[0.18em] text-brand hover:underline"
            >
              <span>General Multi-Service RFQ</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </Shell>
      </section>
    </>
  );
}
