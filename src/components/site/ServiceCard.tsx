"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import type { DivisionItem } from "@/types";
import { cn } from "@/lib/utils";
import { EASE } from "./primitives";
import { ServiceImageSlider } from "./ServiceImageSlider";

export function ServiceCard({
  service,
  index,
  className,
}: {
  service: DivisionItem;
  index: number;
  className?: string;
}) {
  const reduce = useReducedMotion();

  return (
    <motion.article
      id={service.id}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-[2px] border border-line bg-paper-2 transition-all duration-300 hover:border-brand/60 hover:shadow-lg",
        className
      )}
      initial={{ opacity: 0, y: reduce ? 0 : 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-6% 0px" }}
      transition={{ duration: 0.6, delay: (index % 3) * 0.08, ease: EASE }}
    >
      <Link
        href={`/services/${service.id}`}
        className="relative block aspect-[4/3] w-full overflow-hidden bg-panel focus:outline-none focus:ring-2 focus:ring-brand"
        aria-label={`View ${service.name} commercial service details`}
      >
        <ServiceImageSlider
          images={service.images}
          fallbackImage={service.image}
          alt={`${service.name} — EDEN BOUNTY commercial service`}
          staggerIndex={index}
        />
        <div
          className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/25 to-black/10 transition-opacity duration-300 group-hover:from-black/90 pointer-events-none"
          aria-hidden="true"
        />

        {/* Minimal Title & Indicator */}
        <div className="absolute inset-x-5 bottom-4 flex items-end justify-between gap-3 pointer-events-none">
          <div className="min-w-0">
            <span className="block font-mono text-[0.58rem] uppercase tracking-[0.22em] text-brand">
              {service.sector || "Commercial Service"}
            </span>
            <h3 className="eb-display text-[1.45rem] sm:text-[1.65rem] font-bold leading-tight text-white drop-shadow-sm truncate">
              {service.name}
            </h3>
          </div>
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-white backdrop-blur-sm transition-transform duration-300 group-hover:bg-brand group-hover:text-brand-ink group-hover:translate-x-0.5 group-hover:-translate-y-0.5">
            <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
          </span>
        </div>
      </Link>

      {/* Card Action Bar */}
      <div className="flex items-center justify-between border-t border-line/80 px-4 py-2.5 bg-paper/50">
        <Link
          href={`/services/${service.id}`}
          className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-ink-muted hover:text-brand transition-colors"
        >
          View details →
        </Link>
        <Link
          href={`/rfq?division=${service.id}`}
          className="font-mono text-[0.68rem] uppercase tracking-[0.16em] text-brand hover:underline font-semibold"
          aria-label={`Enquire about ${service.name}`}
        >
          Enquire
        </Link>
      </div>

      <span
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[2px] origin-left scale-x-0 bg-brand transition-transform duration-500 group-hover:scale-x-100"
        aria-hidden="true"
      />
    </motion.article>
  );
}
