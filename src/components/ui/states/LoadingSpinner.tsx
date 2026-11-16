"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
  fullPage?: boolean;
}

export function LoadingSpinner({
  size = "md",
  label = "Loading...",
  className,
  fullPage = false,
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "h-3.5 w-3.5",
    md: "h-5 w-5",
    lg: "h-8 w-8",
  };

  const content = (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center justify-center gap-2.5 text-brand ",
        className
      )}
    >
      <Loader2 className={cn("animate-spin shrink-0", sizeClasses[size])} />
      {label && (
        <span className="font-mono text-xs uppercase tracking-wider text-ink-subtle">
          {label}
        </span>
      )}
      <span className="sr-only">{label}</span>
    </div>
  );

  if (fullPage) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center p-8">
        {content}
      </div>
    );
  }

  return content;
}
