import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site/SiteHeader";
import { SiteFooter } from "@/components/site/SiteFooter";
import { ButtonLink, Shell } from "@/components/site/primitives";
import { SeaContours } from "@/components/site/SeaContours";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <div className="eb-backdrop flex min-h-dvh flex-col text-ink">
      <SiteHeader />
      <main id="main" className="relative isolate flex flex-1 items-center overflow-hidden pb-20 pt-36">
        <SeaContours lines={5} top={55} step={8} />
        <Shell>
          <div className="eb-glass max-w-2xl p-8 sm:p-12">
            <p className="eb-eyebrow">
              <span className="text-brand">404</span> — Off course
            </p>
            <h1 className="eb-display mt-6 text-[clamp(2.6rem,6vw,4.5rem)] text-ink">This page isn&rsquo;t on our charts.</h1>
            <p className="mt-5 text-ink-muted">The address may be mistyped, or the page may have moved.</p>
            <div className="mt-10 flex flex-wrap gap-4">
              <ButtonLink href="/">Return home</ButtonLink>
              <ButtonLink href="/rfq" variant="ghost">
                Contact us
              </ButtonLink>
            </div>
            <p className="mt-8 text-sm text-ink-subtle">
              Or browse <Link href="/services" className="underline decoration-brand underline-offset-4 hover:text-brand">our commercial divisions</Link>.
            </p>
          </div>
        </Shell>
      </main>
      <SiteFooter />
    </div>
  );
}
