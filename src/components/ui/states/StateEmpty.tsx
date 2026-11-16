"use client";

import React from "react";
import { Inbox, SearchX, RotateCcw, Plus, LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StateEmptyProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  isFiltered?: boolean;
  primaryAction?: {
    label: string;
    onClick: () => void;
    icon?: LucideIcon;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  compact?: boolean;
}

export function StateEmpty({
  icon: CustomIcon,
  title,
  description,
  isFiltered = false,
  primaryAction,
  secondaryAction,
  className,
  compact = false,
}: StateEmptyProps) {
  const Icon = CustomIcon || (isFiltered ? SearchX : Inbox);

  return (
    <div
      role="status"
      aria-label={title}
      className={cn(
        "rounded-[2px] border border-line-strong  bg-panel  text-center shadow-sm flex flex-col items-center justify-center",
        compact ? "p-6" : "p-8 sm:p-12",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-[2px] bg-panel-2 border border-line text-ink-subtle mb-4">
        <Icon className="h-6 w-6" />
      </div>

      <div className="max-w-md space-y-1.5">
        <h3 className="font-heading text-sm sm:text-base font-bold uppercase tracking-wider text-ink">
          {title}
        </h3>
        <p className="font-body text-xs text-ink-subtle leading-relaxed">
          {description}
        </p>
      </div>

      {isFiltered && (
        <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-panel-2 border border-line text-[10px] font-mono text-ink-subtle">
          <span>Filtered Query Result</span>
        </div>
      )}

      {(primaryAction || secondaryAction) && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {primaryAction && (
            <button
              type="button"
              onClick={primaryAction.onClick}
              className="inline-flex min-h-[44px] items-center gap-2 px-4 py-2 rounded-[2px] bg-brand font-heading text-xs font-semibold uppercase tracking-wider text-brand-ink hover:bg-brand-hover transition-all cursor-pointer shadow-sm"
            >
              {primaryAction.icon ? (
                <primaryAction.icon className="h-4 w-4" />
              ) : isFiltered ? (
                <RotateCcw className="h-4 w-4" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              <span>{primaryAction.label}</span>
            </button>
          )}

          {secondaryAction && (
            <button
              type="button"
              onClick={secondaryAction.onClick}
              className="inline-flex min-h-[44px] items-center px-4 py-2 rounded-[2px] border border-line-strong font-heading text-xs font-semibold uppercase tracking-wider text-ink-muted hover:bg-panel-2 transition-colors cursor-pointer"
            >
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
