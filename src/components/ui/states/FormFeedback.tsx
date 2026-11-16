"use client";

import React from "react";
import { AlertCircle, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FormFieldErrorProps {
  id?: string;
  error?: string | null;
  className?: string;
}

export function FormFieldError({ id, error, className }: FormFieldErrorProps) {
  if (!error) return null;

  return (
    <div
      id={id}
      role="alert"
      aria-live="polite"
      className={cn(
        "flex items-center gap-1.5 mt-1.5 text-xs text-[#DC2626] dark:text-[#EF4444] animate-in fade-in duration-150",
        className
      )}
    >
      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
      <span className="font-body leading-tight">{error}</span>
    </div>
  );
}

export interface FormErrorSummaryProps {
  errors: Record<string, string | undefined>;
  title?: string;
  onFieldClick?: (fieldName: string) => void;
  className?: string;
}

export function FormErrorSummary({
  errors,
  title = "Please Correct the Following Fields",
  onFieldClick,
  className,
}: FormErrorSummaryProps) {
  const activeErrors = Object.entries(errors).filter(
    ([, msg]) => Boolean(msg)
  ) as [string, string][];

  if (activeErrors.length === 0) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "rounded-[2px] border border-[#FCA5A5] dark:border-[#7F1D1D] bg-[#FEF2F2] dark:bg-[#1A0A0C] p-4 text-xs shadow-sm space-y-2 mb-4 animate-in fade-in duration-200",
        className
      )}
    >
      <div className="flex items-center gap-2 text-[#991B1B] dark:text-[#FCA5A5] font-heading font-bold uppercase tracking-wider text-[11px] sm:text-xs">
        <AlertTriangle className="h-4 w-4 shrink-0 text-[#DC2626] dark:text-[#EF4444]" />
        <span>{title} ({activeErrors.length} {activeErrors.length === 1 ? "error" : "errors"})</span>
      </div>

      <ul className="list-disc list-inside space-y-1 font-body text-[#B91C1C] dark:text-[#F87171] pl-1">
        {activeErrors.map(([field, message]) => (
          <li key={field}>
            {onFieldClick ? (
              <button
                type="button"
                onClick={() => onFieldClick(field)}
                className="underline hover:text-[#991B1B] dark:hover:text-[#FCA5A5] cursor-pointer text-left focus-visible:outline-1"
              >
                {message}
              </button>
            ) : (
              <span>{message}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Returns accessible styling classes for inputs based on validation state.
 */
export function getInputValidationClasses(hasError: boolean): string {
  if (hasError) {
    return cn(
      "border-[#DC2626] dark:border-[#EF4444]",
      "bg-[#FEF2F2]/30 dark:bg-[#200A0D]/40",
      "text-ink ",
      "focus:border-[#DC2626] dark:focus:border-[#EF4444]",
      "focus:ring-1 focus:ring-[#DC2626] dark:focus:ring-[#EF4444]"
    );
  }

  return cn(
    "border-line-strong ",
    "bg-panel ",
    "text-ink ",
    "focus:border-brand ",
    "focus:ring-1 focus:ring-brand "
  );
}
