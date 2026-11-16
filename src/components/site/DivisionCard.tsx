"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import type { DivisionItem } from "@/types";
import { cn } from "@/lib/utils";
import { EASE } from "./primitives";
import { ServiceImageSlider } from "./ServiceImageSlider";

export function DivisionCard({
  division,
  index,
  detailed = false,
  className,
}: {
  division: DivisionItem;
  index: number;
  detailed?: boolean;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.article
      id={detailed ? division.id : undefined}
      className={cn("group relative flex scroll-mt-28 flex-col overflow-hidden eb-glass eb-glass-hover", className)}
      initial={{ opacity: 0, y: reduce ? 0 : 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-8% 0px" }}
      transition={{ duration: 0.8, delay: (index % 3) * 0.08, ease: EASE }}
    >
      <div className="relative aspect-[4/3] overflow-hidden">
        <ServiceImageSlider
          images={division.images}
          fallbackImage={division.image}
          alt={`${division.name} — EDEN BOUNTY commercial service`}
          staggerIndex={index}
        />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,transparent_45%,rgb(var(--eb-scrim)/0.85))] pointer-events-none" aria-hidden="true" />
      </div>
      <div className="flex flex-1 flex-col p-6">
        <div className="flex items-start justify-between gap-4">
          <h3 className="eb-display text-[1.9rem] leading-tight text-ink">{division.name}</h3>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-ink-muted">{division.description}</p>
        {detailed && division.highlights && (
          <ul className="mt-5 space-y-2 border-t border-line pt-5">
            {division.highlights.map((h) => (
              <li key={h} className="flex gap-3 text-sm text-ink-muted">
                <span className="mt-2 h-px w-3 shrink-0 bg-brand" aria-hidden="true" />
                {h}
              </li>
            ))}
          </ul>
        )}
        <Link
          href={`/rfq?division=${division.id}`}
          className="mt-auto flex items-center justify-between pt-6 font-mono text-[0.68rem] uppercase tracking-[0.2em] text-ink transition-colors hover:text-brand"
          aria-label={`Enquire about ${division.name}`}
        >
          <span>Enquire</span>
          <ArrowUpRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" />
        </Link>
      </div>
      <span className="pointer-events-none absolute inset-x-0 bottom-0 h-px origin-left scale-x-0 bg-brand transition-transform duration-500 group-hover:scale-x-100" aria-hidden="true" />
    </motion.article>
  );
}
