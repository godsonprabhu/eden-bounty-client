import Link from "next/link";
import { siteConfig } from "@/config/site";
import { businessDivisions } from "@/data/divisions";
import { SITE_NAV } from "./nav";
import { Shell, Wordmark } from "./primitives";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="eb-glass-strong relative !border-x-0 !border-b-0">
      <Shell className="py-16 sm:py-20">
        <div className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <Wordmark />
            <p className="eb-display mt-8 max-w-md text-3xl text-ink sm:text-4xl">
              Wholesale trade, conducted with clarity.
            </p>
            <a
              href={`mailto:${siteConfig.contact.email}`}
              className="mt-8 inline-block border-b border-brand pb-1 font-mono text-sm text-ink transition-colors hover:text-brand"
            >
              {siteConfig.contact.email}
            </a>
          </div>

          <nav aria-label="Footer" className="grid grid-cols-2 gap-10 sm:grid-cols-3 lg:col-span-7">
            <div>
              <p className="eb-eyebrow">Navigate</p>
              <ul className="mt-5 space-y-3 text-sm">
                {SITE_NAV.map((n) => (
                  <li key={n.href}>
                    <Link href={n.href} className="text-ink-muted transition-colors hover:text-brand">
                      {n.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <div className="sm:col-span-1">
              <p className="eb-eyebrow">Services</p>
              <ul className="mt-5 space-y-3 text-sm">
                {businessDivisions.slice(0, 6).map((d) => (
                  <li key={d.id}>
                    <Link href={`/services/${d.id}`} className="text-ink-muted transition-colors hover:text-brand">
                      {d.name}
                    </Link>
                  </li>
                ))}
                <li>
                  <Link href="/services" className="text-brand">
                    All services →
                  </Link>
                </li>
              </ul>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <p className="eb-eyebrow">Registered office</p>
              <address className="mt-5 text-sm not-italic leading-relaxed text-ink-muted">
                {siteConfig.contact.address}
              </address>
              <p className="mt-4 font-mono text-xs text-ink-subtle">SSM {siteConfig.contact.registrationNumber}</p>
            </div>
          </nav>
        </div>

        <div className="mt-16 flex flex-col gap-3 border-t border-line pt-6 font-mono text-[0.68rem] tracking-[0.18em] text-ink-subtle sm:flex-row sm:items-center sm:justify-between">
          <p>© {year} {siteConfig.legalName}</p>
          <p className="uppercase">Shah Alam · Selangor · Malaysia</p>
        </div>
      </Shell>
    </footer>
  );
}
