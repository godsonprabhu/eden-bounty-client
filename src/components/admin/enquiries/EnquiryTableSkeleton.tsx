"use client";

import React from "react";

export function EnquiryTableSkeleton() {
  return (
    <div className="rounded-[2px] border border-line bg-panel shadow-2xs overflow-hidden animate-pulse">
      {/* Table Header Skeleton */}
      <div className="h-10 bg-panel-2 border-b border-line flex items-center px-4 gap-6">
        <div className="h-3 w-20 bg-line-strong rounded-[2px]" />
        <div className="h-3 w-32 bg-line-strong rounded-[2px]" />
        <div className="h-3 w-28 bg-line-strong rounded-[2px]" />
        <div className="h-3 w-36 bg-line-strong rounded-[2px]" />
        <div className="h-3 w-20 bg-line-strong rounded-[2px]" />
        <div className="h-3 w-28 bg-line-strong rounded-[2px]" />
        <div className="h-3 w-16 bg-line-strong rounded-[2px] ml-auto" />
      </div>

      {/* Rows Skeleton */}
      <div className="divide-y divide-panel-2">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="py-4 px-4 flex items-center gap-6">
            <div className="h-4 w-24 bg-line rounded-[2px]" />
            <div className="h-4 w-32 bg-line rounded-[2px]" />
            <div className="h-4 w-28 bg-line rounded-[2px]" />
            <div className="space-y-1.5 w-36">
              <div className="h-3.5 w-full bg-line rounded-[2px]" />
              <div className="h-2.5 w-20 bg-line rounded-[2px]" />
            </div>
            <div className="h-5 w-20 bg-line rounded-[2px]" />
            <div className="h-5 w-24 bg-line rounded-[2px]" />
            <div className="h-6 w-24 bg-line rounded-[2px] ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}
