"use client";

import React from "react";
import { AlertCircle, RefreshCw, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Sanitizes backend error strings to guarantee that stack traces, SQL,
 * internal filesystem paths, or backend exception details are never exposed to users.
 */
export function sanitizeErrorMessage(rawError: unknown, statusCode?: number): string {
  if (statusCode === 401) {
    return "Your administrative session has expired or authentication credentials were not recognized. Please sign in again.";
  }
  if (statusCode === 403) {
    return "Access Denied: You do not possess sufficient authorization to perform this operation or inspect this resource.";
  }
  if (statusCode === 404) {
    return "The requested record or resource was not found in the commercial registry.";
  }
  if (statusCode === 409) {
    return "A state conflict occurred. The record may have been modified concurrently by another process. Please refresh and review.";
  }
  if (statusCode === 422) {
    return "The submitted data contains invalid field values. Please review the highlighted fields and retry.";
  }
  if (statusCode === 429) {
    return "Request threshold exceeded. Temporary rate-limiting is active to protect system availability. Please wait before retrying.";
  }
  if (statusCode && statusCode >= 500) {
    return "An internal server error occurred while processing your request. The operations desk has been notified. Please retry momentarily.";
  }

  const rawStr =
    typeof rawError === "string"
      ? rawError
      : rawError instanceof Error
      ? rawError.message
      : "";

  if (!rawStr) {
    return "An unexpected error occurred while communicating with the server. Please try again.";
  }

  // Detect sensitive technical patterns
  const sensitivePatterns = [
    /traceback/i,
    /psycopg/i,
    /sqlalchemy/i,
    /internal server error/i,
    /syntax error/i,
    /pg_catalog/i,
    /select\s+.*?\s+from/i,
    /insert\s+into/i,
    /update\s+.*?\s+set/i,
    /delete\s+from/i,
    /\/home\//i,
    /\/app\//i,
    /\.py:\d+/i,
    /exception\s+in/i,
  ];

  for (const pattern of sensitivePatterns) {
    if (pattern.test(rawStr)) {
      return "A database or system service error occurred. Sensitive technical details have been suppressed for security. Please retry or contact support.";
    }
  }

  return rawStr;
}

export interface StateErrorProps {
  title?: string;
  error?: unknown;
  message?: string;
  statusCode?: number;
  onRetry?: () => void;
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  compact?: boolean;
  className?: string;
}

export function StateError({
  title = "System Request Failed",
  error,
  message,
  statusCode,
  onRetry,
  secondaryAction,
  compact = false,
  className,
}: StateErrorProps) {
  const displayMessage = sanitizeErrorMessage(message || error, statusCode);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "rounded-[2px] border border-[#FCA5A5] dark:border-[#7F1D1D] bg-[#FEF2F2] dark:bg-[#1A0A0C] text-center shadow-sm flex flex-col items-center justify-center",
        compact ? "p-5" : "p-8 sm:p-10",
        className
      )}
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-[2px] bg-[#FEE2E2] dark:bg-[#2D0D11] border border-[#F87171] text-[#DC2626] dark:text-[#EF4444] mb-3">
        <AlertCircle className="h-6 w-6" />
      </div>

      <div className="max-w-md space-y-1">
        <h3 className="font-heading text-sm sm:text-base font-bold uppercase tracking-wider text-[#991B1B] dark:text-[#FCA5A5]">
          {title}
        </h3>
        <p className="font-body text-xs text-[#B91C1C] dark:text-[#F87171] leading-relaxed">
          {displayMessage}
        </p>
      </div>

      {statusCode && (
        <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-[2px] bg-[#FEE2E2] dark:bg-[#2D0D11] border border-[#FCA5A5]/60 text-[10px] font-mono text-[#991B1B] dark:text-[#FCA5A5]">
          <span>HTTP {statusCode}</span>
        </div>
      )}

      {(onRetry || secondaryAction) && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex min-h-[44px] items-center gap-2 px-4 py-2 rounded-[2px] bg-[#DC2626] dark:bg-[#EF4444] font-heading text-xs font-semibold uppercase tracking-wider text-white hover:bg-[#B91C1C] dark:hover:bg-[#DC2626] transition-all cursor-pointer shadow-sm"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Retry Operation</span>
            </button>
          )}

          {secondaryAction && (
            <button
              type="button"
              onClick={secondaryAction.onClick}
              className="inline-flex min-h-[44px] items-center gap-1.5 px-4 py-2 rounded-[2px] border border-[#F87171] font-heading text-xs font-semibold uppercase tracking-wider text-[#991B1B] dark:text-[#FCA5A5] hover:bg-[#FEE2E2] dark:hover:bg-[#2D0D11] transition-colors cursor-pointer"
            >
              <span>{secondaryAction.label}</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
