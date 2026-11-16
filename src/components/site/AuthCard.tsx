import { BrandMark, Shell } from "@/components/site/primitives";

/** Single-column glass card used by the password pages; matches the investor login styling. */
export function AuthCard({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="relative isolate flex min-h-[100dvh] items-center overflow-hidden pb-16 pt-28 sm:pt-32">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <div className="absolute left-[8%] top-[14%] h-[30vmax] w-[30vmax] rounded-full bg-[radial-gradient(circle,color-mix(in_oklab,var(--eb-brand)_36%,transparent),transparent_65%)] blur-2xl" />
        <div className="eb-grid absolute inset-0 opacity-25 [mask-image:radial-gradient(55%_55%_at_50%_45%,black,transparent)]" />
      </div>
      <Shell>
        <div className="eb-glass mx-auto w-full max-w-[560px] p-8 sm:p-10">
          <div className="flex items-center gap-3 text-ink">
            <BrandMark className="h-9 w-9" />
            <span className="text-[0.8rem] font-semibold tracking-[0.32em]">EDEN BOUNTY</span>
          </div>
          <p className="eb-eyebrow mt-8">{eyebrow}</p>
          <h1 className="eb-display mt-4 text-[2.4rem] leading-tight text-ink">{title}</h1>
          {intro && <div className="mt-3 text-sm leading-relaxed text-ink-muted">{intro}</div>}
          {children}
        </div>
      </Shell>
    </section>
  );
}

export const authInputCls =
  "eb-glass-inset block min-h-[3.25rem] w-full pl-11 pr-4 text-[0.95rem] text-ink placeholder:text-ink-subtle/80 transition-[border-color,box-shadow] duration-300 focus-visible:border-brand focus-visible:shadow-[0_0_0_4px_var(--eb-glow)] focus-visible:outline-none disabled:opacity-50";

export const authButtonCls =
  "group flex min-h-[3.25rem] w-full cursor-pointer items-center justify-center gap-3 bg-brand px-5 text-[0.8rem] font-semibold uppercase tracking-[0.18em] text-brand-ink transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60";

export const authLabelCls = "mb-2 block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted";

export function AuthAlert({ tone, children }: { tone: "error" | "ok"; children: React.ReactNode }) {
  const cls =
    tone === "error"
      ? "border-[#FCA5A5] bg-[#FEF2F2]/90 text-[#B91C1C] dark:border-[#7F1D1D] dark:bg-[#1A0A0C]/80 dark:text-[#F87171]"
      : "border-emerald-600/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300";
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`mt-6 border p-3.5 text-sm leading-relaxed ${cls}`}>
      {children}
    </div>
  );
}
