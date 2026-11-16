"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { HeroOcean } from "@/components/hero/HeroOcean";
import { ButtonLink, EASE, RevealWords, Shell } from "@/components/site/primitives";
import { siteConfig } from "@/config/site";

export function HomeHero() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const contentY = useTransform(scrollY, [0, 600], [0, reduce ? 0 : -60]);
  const contentOpacity = useTransform(scrollY, [0, 500], [1, reduce ? 1 : 0.15]);

  return (
    <section className="relative isolate flex min-h-[max(100dvh,680px)] flex-col overflow-hidden bg-paper" aria-labelledby="hero-title">
      <HeroOcean />

      {/* Legibility scrims */}
      <div
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgb(var(--eb-scrim)/0.9)_0%,rgb(var(--eb-scrim)/0.55)_38%,transparent_62%)] md:bg-[linear-gradient(90deg,rgb(var(--eb-scrim)/0.94)_0%,rgb(var(--eb-scrim)/0.7)_30%,rgb(var(--eb-scrim)/0)_58%)]"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-[linear-gradient(180deg,rgb(var(--eb-scrim)/0.85),transparent)]" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-56 bg-[linear-gradient(0deg,rgb(var(--eb-scrim)/0.92),transparent)]" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 shadow-[inset_0_0_220px_rgba(0,0,0,0.45)] dark:shadow-[inset_0_0_260px_rgba(0,0,0,0.85)]" aria-hidden="true" />
      <div className="eb-grain" aria-hidden="true" />

      {/* Hairline layout grid */}
      <div className="pointer-events-none absolute inset-0 hidden lg:block" aria-hidden="true">
        <Shell className="relative h-full">
          <span className="absolute inset-y-0 left-12 w-px bg-ink/8" />
          <span className="absolute inset-y-0 right-12 w-px bg-ink/8" />
        </Shell>
      </div>

      <motion.div style={{ y: contentY, opacity: contentOpacity }} className="relative z-10 flex flex-1 flex-col">
        <Shell className="flex flex-1 flex-col justify-start pb-[34vh] pt-28 sm:pt-40 md:pb-16 lg:justify-center lg:pb-0 lg:pt-24">
          <div className="max-w-[640px]">
            <motion.p
              className="eb-eyebrow flex items-center gap-3 whitespace-nowrap"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 1, delay: 0.2 }}
            >
              Wholesale trading<span className="max-sm:hidden"> · Malaysia</span>
            </motion.p>

            <h1 id="hero-title" className="eb-display mt-7 text-[clamp(3rem,7.4vw,6.6rem)] text-ink">
              <RevealWords text="Wholesale trade," delay={0.3} />{" "}
              <em className="text-brand">
                <RevealWords text="steered with" delay={0.45} />
              </em>{" "}
              <RevealWords text="precision." delay={0.6} />
            </h1>

            <motion.p
              className="mt-7 max-w-[30rem] text-base leading-relaxed text-ink-muted sm:text-lg"
              initial={{ opacity: 0, y: reduce ? 0 : 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, delay: 0.9, ease: EASE }}
            >
              {siteConfig.legalName} is a Malaysia-based wholesale trading and business solutions company,
              coordinating commercial enquiries across its trading services under documented, mutually agreed terms.
            </motion.p>

            <motion.div
              className="mt-10 flex flex-wrap items-center gap-4"
              initial={{ opacity: 0, y: reduce ? 0 : 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, delay: 1.05, ease: EASE }}
            >
              <ButtonLink href="/rfq">Start a trade enquiry</ButtonLink>
              <ButtonLink href="/services" variant="ghost">
                Explore services
              </ButtonLink>
            </motion.div>
          </div>
        </Shell>

        {/* Supporting company information */}
        <motion.div
          className="relative border-t border-ink/10"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2, delay: 1.3 }}
        >
          <Shell>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-5 py-6 sm:py-7 md:grid-cols-4">
              {[
                ["Registered entity", siteConfig.legalName],
                ["SSM registration", siteConfig.contact.registrationNumber ?? "—"],
                ["Head office", "Shah Alam, Selangor"],
                ["Commercial channel", siteConfig.contact.email],
              ].map(([k, v]) => (
                <div key={k} className="min-w-0">
                  <dt className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-subtle">{k}</dt>
                  <dd className="mt-1.5 truncate text-sm text-ink" title={v}>
                    {v}
                  </dd>
                </div>
              ))}
            </dl>
          </Shell>
        </motion.div>
      </motion.div>
    </section>
  );
}
