import { RevealWords, Shell } from "./primitives";
import { SeaContours } from "./SeaContours";

/** Inner-page masthead with drifting sea contours. */
export function PageHero({
  index,
  eyebrow,
  title,
  intro,
  children,
}: {
  index?: string;
  eyebrow: string;
  title: string;
  intro: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="relative isolate overflow-hidden border-b border-line bg-paper-2 pb-20 pt-40 sm:pb-24 sm:pt-48">
      <SeaContours />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(70%_60%_at_80%_20%,var(--eb-glow),transparent_70%)]" aria-hidden="true" />
      <div className="eb-grain" aria-hidden="true" />
      <Shell>
        <p className="eb-eyebrow flex items-center gap-3">
          {index && (
            <>
              <span className="text-brand">{index}</span>
              <span className="h-px w-10 bg-line-strong" aria-hidden="true" />
            </>
          )}
          {eyebrow}
        </p>
        <h1 className="eb-display mt-7 max-w-4xl text-[clamp(3rem,7vw,6rem)] text-ink">
          <RevealWords text={title} delay={0.1} />
        </h1>
        <p className="mt-7 max-w-2xl text-base leading-relaxed text-ink-muted sm:text-lg">{intro}</p>
        {children}
      </Shell>
    </section>
  );
}
