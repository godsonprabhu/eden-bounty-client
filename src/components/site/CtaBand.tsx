import { siteConfig } from "@/config/site";
import { ButtonLink, Reveal, Shell } from "./primitives";

export function CtaBand() {
  return (
    <section className="relative isolate overflow-hidden">
      <div className="eb-grid absolute inset-0 -z-10 opacity-40 [mask-image:radial-gradient(70%_80%_at_50%_50%,black,transparent)]" aria-hidden="true" />
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(50%_70%_at_50%_100%,var(--eb-glow),transparent_70%)]" aria-hidden="true" />
      <Shell className="eb-section text-center">
        <Reveal>
          <p className="eb-eyebrow">Commercial enquiries</p>
          <h2 className="eb-display mx-auto mt-6 max-w-4xl text-[clamp(2.6rem,6vw,5.4rem)] text-ink">
            Set a course for your <em className="text-brand">next</em> trade.
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-base text-ink-muted sm:text-lg">
            Submit an RFQ online or prepare an email draft. Commercial quotations are provided upon request, subject to review.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <ButtonLink href="/rfq">Open the enquiry desk</ButtonLink>
            <ButtonLink href={`mailto:${siteConfig.contact.email}`} variant="ghost">
              {siteConfig.contact.email}
            </ButtonLink>
          </div>
        </Reveal>
      </Shell>
    </section>
  );
}
