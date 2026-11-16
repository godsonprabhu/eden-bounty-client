"use client";

import Link from "next/link";
import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

export const EASE = [0.22, 1, 0.36, 1] as const;

/* ------------------------------ Logo ------------------------------ */

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-8 w-8 shrink-0", className)} aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="none" stroke="currentColor" strokeOpacity="0.35" />
      <path d="M5 18.5c3.6 0 3.6-1.6 7.2-1.6s3.6 1.6 7.2 1.6 3.6-1.6 7.6-1.6" fill="none" stroke="var(--eb-brand)" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M9 14.2h12.5l2.5-2.4H11.5z" fill="currentColor" />
      <path d="M12 11.6V8.4h3.2v3.2" fill="none" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

export function Wordmark({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-3 text-ink", className)}>
      <BrandMark />
      <span className="flex flex-col leading-none">
        <span className="text-[0.82rem] font-semibold tracking-[0.32em]">EDEN BOUNTY</span>
        {!compact && (
          <span className="mt-1.5 font-mono text-[0.58rem] tracking-[0.24em] text-ink-subtle">Sdn. Bhd. · Malaysia</span>
        )}
      </span>
    </span>
  );
}

/* ----------------------------- Buttons ---------------------------- */

type ButtonProps = {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  className?: string;
  external?: boolean;
};

export function ButtonLink({ href, children, variant = "primary", className, external }: ButtonProps) {
  const base =
    "group relative inline-flex min-h-12 items-center justify-center gap-3 overflow-hidden px-6 text-[0.78rem] font-semibold uppercase tracking-[0.16em] transition-[background-color,color,border-color,box-shadow] duration-300 ease-[var(--ease-tide)] cursor-pointer";
  const styles =
    variant === "primary"
      ? "bg-brand text-brand-ink hover:bg-brand-hover shadow-[0_10px_40px_-12px_var(--eb-glow)]"
      : "border border-line-strong text-ink hover:border-brand hover:text-brand bg-transparent";
  const content = (
    <>
      <span>{children}</span>
      <ArrowUpRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" />
    </>
  );
  if (external || href.startsWith("mailto:")) {
    return (
      <a href={href} className={cn(base, styles, className)} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
        {content}
      </a>
    );
  }
  return (
    <Link href={href} className={cn(base, styles, className)}>
      {content}
    </Link>
  );
}

/* ----------------------------- Reveal ----------------------------- */

type RevealProps = HTMLMotionProps<"div"> & { delay?: number; y?: number };

export function Reveal({ delay = 0, y = 28, className, children, ...rest }: RevealProps) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px" }}
      transition={{ duration: reduce ? 0.2 : 0.9, delay, ease: EASE }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Staggered word reveal for display headings. */
export function RevealWords({ text, className, delay = 0 }: { text: string; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  const words = text.split(" ");
  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      {words.map((w, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.12em] align-bottom" aria-hidden="true">
          <motion.span
            className="inline-block"
            initial={reduce ? { opacity: 0 } : { y: "105%" }}
            animate={reduce ? { opacity: 1 } : { y: "0%" }}
            transition={{ duration: 1.05, delay: delay + i * 0.07, ease: EASE }}
          >
            {w}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </span>
  );
}

/* -------------------------- Section header ------------------------ */

export function SectionHeader({
  index,
  eyebrow,
  title,
  intro,
  className,
  align = "left",
}: {
  index?: string;
  eyebrow: string;
  title: React.ReactNode;
  intro?: React.ReactNode;
  className?: string;
  align?: "left" | "split";
}) {
  return (
    <Reveal
      className={cn(
        align === "split" ? "grid gap-8 lg:grid-cols-12 lg:items-end" : "max-w-3xl",
        className
      )}
    >
      <div className={align === "split" ? "lg:col-span-7" : undefined}>
        <p className="eb-eyebrow flex items-center gap-3">
          {index && (
            <>
              <span className="text-brand">{index}</span>
              <span className="h-px w-8 bg-line-strong" aria-hidden="true" />
            </>
          )}
          <span>{eyebrow}</span>
        </p>
        <h2 className="eb-display mt-6 text-[clamp(2.4rem,5vw,4.25rem)] text-ink">{title}</h2>
      </div>
      {intro && (
        <p
          className={cn(
            "text-base leading-relaxed text-ink-muted sm:text-lg",
            align === "split" ? "lg:col-span-5 lg:pb-3" : "mt-6 max-w-2xl"
          )}
        >
          {intro}
        </p>
      )}
    </Reveal>
  );
}

export function Shell({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1380px] px-4 sm:px-8 lg:px-12", className)}>{children}</div>;
}
