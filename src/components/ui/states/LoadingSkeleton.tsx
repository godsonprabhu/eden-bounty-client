"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface SkeletonProps {
  className?: string;
}

export function SkeletonBox({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse motion-reduce:animate-none rounded-[2px] bg-line ",
        className
      )}
    />
  );
}

export function SkeletonText({
  lines = 1,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div aria-hidden="true" className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, idx) => (
        <div
          key={idx}
          className={cn(
            "h-3.5 rounded-[2px] bg-line  animate-pulse motion-reduce:animate-none",
            idx === lines - 1 && lines > 1 ? "w-2/3" : "w-full"
          )}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-[2px] border border-line  bg-panel  p-5 space-y-4 shadow-sm",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <SkeletonBox className="h-4 w-32" />
        <SkeletonBox className="h-4 w-16" />
      </div>
      <SkeletonBox className="h-8 w-24" />
      <SkeletonText lines={2} />
    </div>
  );
}

export function SkeletonMetricsGrid({ count = 4 }: { count?: number }) {
  return (
    <div
      aria-hidden="true"
      className="grid grid-cols-2 lg:grid-cols-4 gap-4"
    >
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="rounded-[2px] border border-line bg-panel p-4 space-y-2 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <SkeletonBox className="h-3 w-20" />
            <SkeletonBox className="h-3 w-3 rounded-full" />
          </div>
          <SkeletonBox className="h-7 w-16" />
          <SkeletonBox className="h-2.5 w-24" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({
  rows = 5,
  columns = 5,
  className,
}: {
  rows?: number;
  columns?: number;
  className?: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-[2px] border border-line  bg-panel  overflow-hidden shadow-sm",
        className
      )}
    >
      {/* Table Header */}
      <div className="border-b border-line bg-panel-2 px-4 py-3 flex items-center justify-between gap-4">
        {Array.from({ length: columns }).map((_, idx) => (
          <SkeletonBox
            key={idx}
            className={cn("h-3.5", idx === 0 ? "w-28" : "w-20")}
          />
        ))}
      </div>

      {/* Table Rows */}
      <div className="divide-y divide-line">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div
            key={rowIdx}
            className="px-4 py-3.5 flex items-center justify-between gap-4"
          >
            {Array.from({ length: columns }).map((_, colIdx) => (
              <SkeletonBox
                key={colIdx}
                className={cn(
                  "h-3",
                  colIdx === 0
                    ? "w-32"
                    : colIdx === 1
                    ? "w-24"
                    : colIdx === 2
                    ? "w-16"
                    : "w-20"
                )}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
