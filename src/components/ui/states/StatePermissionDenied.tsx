"use client";

import React from "react";
import Link from "next/link";
import { ShieldAlert, ArrowLeft, LogIn } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StatePermissionDeniedProps {
  title?: string;
  message?: string;
  requiredRole?: string;
  onReturn?: () => void;
  className?: string;
  compact?: boolean;
}

export function StatePermissionDenied({
  title = "Access Restricted",
  message,
  requiredRole = "SUPER_ADMIN",
  onReturn,
  className,
  compact = false,
}: StatePermissionDeniedProps) {
  return (
    <div
      role="alert"
      aria-label={title}
      className={cn(
        "rounded-[2px] border border-[#FCA5A5] dark:border-[#7F1D1D] bg-[#FEF2F2] dark:bg-[#1A0A0C] text-center shadow-sm flex flex-col items-center justify-center",
        compact ? "p-6" : "p-8 sm:p-12",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-[2px] bg-[#FEE2E2] dark:bg-[#2D0D11] border border-[#F87171] text-[#DC2626] dark:text-[#EF4444] mb-4">
        <ShieldAlert className="h-6 w-6" />
      </div>

      <div className="max-w-md space-y-1.5">
        <h3 className="font-heading text-sm sm:text-base font-bold uppercase tracking-wider text-[#991B1B] dark:text-[#FCA5A5]">
          {title}
        </h3>
        <p className="font-body text-xs text-[#B91C1C] dark:text-[#F87171] leading-relaxed">
          {message ||
            `This administrative workspace or operation is restricted exclusively to authorized ${requiredRole} credentials. No sensitive or confidential repository data is exposed.`}
        </p>
      </div>

      <div className="mt-3.5 inline-flex items-center gap-1.5 px-3 py-1 rounded-[2px] bg-[#FEE2E2] dark:bg-[#2D0D11] border border-[#F87171]/50 text-[10px] font-mono text-[#991B1B] dark:text-[#FCA5A5]">
        <span>Single Administrator Authority • {requiredRole} Required</span>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {onReturn ? (
          <button
            type="button"
            onClick={onReturn}
            className="inline-flex min-h-[44px] items-center gap-2 px-4 py-2 rounded-[2px] bg-[#DC2626] dark:bg-[#EF4444] font-heading text-xs font-semibold uppercase tracking-wider text-white hover:bg-[#B91C1C] dark:hover:bg-[#DC2626] transition-all cursor-pointer shadow-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Return to Safe Console</span>
          </button>
        ) : (
          <Link
            href="/admin"
            className="inline-flex min-h-[44px] items-center gap-2 px-4 py-2 rounded-[2px] bg-[#DC2626] dark:bg-[#EF4444] font-heading text-xs font-semibold uppercase tracking-wider text-white hover:bg-[#B91C1C] dark:hover:bg-[#DC2626] transition-all cursor-pointer shadow-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Return to Dashboard</span>
          </Link>
        )}

        <Link
          href="/login"
          className="inline-flex min-h-[44px] items-center gap-1.5 px-4 py-2 rounded-[2px] border border-[#F87171] font-heading text-xs font-semibold uppercase tracking-wider text-[#991B1B] dark:text-[#FCA5A5] hover:bg-[#FEE2E2] dark:hover:bg-[#2D0D11] transition-colors cursor-pointer"
        >
          <LogIn className="h-3.5 w-3.5" />
          <span>Administrator Sign In</span>
        </Link>
      </div>
    </div>
  );
}
