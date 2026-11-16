import React from "react";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/site/primitives";

interface CorporateLogoProps {
  size?: "sm" | "md" | "lg";
  showWordmark?: boolean;
  withSubtitle?: boolean;
  /** Retained for API compatibility; colours now follow the active theme tokens. */
  variant?: "light" | "dark";
  className?: string;
  subtitle?: string;
}

/** Admin-console logo, sharing the public site's brand mark and wordmark. */
export function CorporateLogo({
  size = "md",
  showWordmark = true,
  withSubtitle = true,
  className,
  subtitle = "Operations Console",
}: CorporateLogoProps) {
  const mark = { sm: "h-7 w-7", md: "h-8 w-8", lg: "h-10 w-10" }[size];
  return (
    <span className={cn("inline-flex select-none items-center gap-3 text-ink", className)}>
      <BrandMark className={mark} />
      {showWordmark && (
        <span className="flex flex-col leading-none">
          <span className={cn("font-semibold tracking-[0.3em]", size === "lg" ? "text-sm" : "text-[0.78rem]")}>EDEN BOUNTY</span>
          {withSubtitle && (
            <span className="mt-1.5 font-mono text-[0.56rem] uppercase tracking-[0.22em] text-ink-subtle">{subtitle}</span>
          )}
        </span>
      )}
    </span>
  );
}
