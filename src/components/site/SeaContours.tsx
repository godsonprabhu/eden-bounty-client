import { cn } from "@/lib/utils";

function wavePath(amp: number, len: number, y: number) {
  let d = `M0 ${y}`;
  for (let x = 0; x <= 2400; x += len) {
    d += ` Q${x + len / 4} ${y - amp} ${x + len / 2} ${y} T${x + len} ${y}`;
  }
  return d;
}

/** Slowly drifting sea contour lines — shared ambient layer for mastheads and the login page. */
export function SeaContours({ lines = 6, top = 38, step = 10, className }: { lines?: number; top?: number; step?: number; className?: string }) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 -z-10 opacity-70", className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <svg
          key={i}
          className="eb-drift absolute left-0 h-24 w-[200%] text-line-strong"
          style={{ top: `${top + i * step}%`, ["--eb-drift-duration" as string]: `${50 + i * 14}s`, opacity: 0.25 + i * 0.1 }}
          viewBox="0 0 2400 80"
          preserveAspectRatio="none"
        >
          <path d={wavePath(8 + i * 3, 220 + i * 40, 40)} fill="none" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        </svg>
      ))}
    </div>
  );
}
