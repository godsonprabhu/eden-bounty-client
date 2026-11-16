"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StatePartialDataProps {
  sectionName: string;
  message?: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  className?: string;
}

export function StatePartialData({
  sectionName,
  message,
  onRetry,
  isRetrying = false,
  className,
}: StatePartialDataProps) {
  return (
    <div
      role="region"
      aria-label={`${sectionName} (Partial Data Unavailable)`}
      className={cn(
        "rounded-[2px] border border-[#F59E0B]/50 dark:border-[#D97706]/40 bg-[#FFFBEB] dark:bg-[#1A1204] p-5 shadow-sm space-y-3",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[2px] bg-[#F59E0B]/20 text-[#D97706] dark:text-[#F59E0B]">
            <AlertTriangle className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <h4 className="font-heading text-xs sm:text-sm font-bold uppercase tracking-wider text-[#92400E] dark:text-[#FBBF24] truncate">
              {sectionName}: Temporary Degradation
            </h4>
            <p className="font-body text-xs text-[#78350F] dark:text-[#FDE68A] mt-0.5 leading-snug">
              {message ||
                "This specific module could not be loaded. Surrounding pipeline data remains fully intact and accessible."}
            </p>
          </div>
        </div>

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="inline-flex min-h-[36px] items-center gap-1.5 px-3 py-1 rounded-[2px] bg-[#D97706] dark:bg-[#F59E0B] font-heading text-[11px] font-semibold uppercase tracking-wider text-brand-ink hover:bg-[#B45309] dark:hover:bg-[#FBBF24] disabled:opacity-50 transition-all cursor-pointer shadow-sm shrink-0"
          >
            <RefreshCw className={cn("h-3 w-3", isRetrying && "animate-spin")} />
            <span>{isRetrying ? "Retrying..." : "Retry Section"}</span>
          </button>
        )}
      </div>

      <div className="text-[10px] font-mono text-[#92400E]/80 dark:text-[#FDE68A]/70 flex items-center gap-1.5 border-t border-[#F59E0B]/20 dark:border-[#D97706]/20 pt-2">
        <span className="h-1.5 w-1.5 rounded-full bg-[#F59E0B] shrink-0" />
        <span>Partial Data Isolation: Other dashboard modules operate without interruption.</span>
      </div>
    </div>
  );
}
