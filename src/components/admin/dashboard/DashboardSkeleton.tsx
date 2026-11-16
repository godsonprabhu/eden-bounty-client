"use client";

import React from "react";

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-pulse">
      {/* Header Skeleton */}
      <div className="p-6 rounded-[2px] border border-line eb-glass">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-2.5">
            <div className="h-4 w-40 bg-line rounded-[2px]" />
            <div className="h-7 w-64 bg-line rounded-[2px]" />
            <div className="h-4 w-96 bg-line rounded-[2px]" />
          </div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-28 bg-line rounded-[2px]" />
            <div className="h-10 w-32 bg-line rounded-[2px]" />
            <div className="h-10 w-24 bg-line rounded-[2px]" />
          </div>
        </div>
      </div>

      {/* Metrics Grid Skeleton */}
      <div className="space-y-4">
        <div className="h-4 w-48 bg-line rounded-[2px]" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
          {/* Total Hero Skeleton */}
          <div className="col-span-2 md:col-span-3 lg:col-span-4 h-24 eb-glass border border-line rounded-[2px] p-5" />

          {/* 8 Status Cards Skeleton */}
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-28 eb-glass border border-line rounded-[2px] p-4 space-y-3"
            >
              <div className="flex justify-between">
                <div className="h-3 w-20 bg-line rounded-[2px]" />
                <div className="h-6 w-6 bg-line rounded-[2px]" />
              </div>
              <div className="h-7 w-12 bg-line rounded-[2px]" />
            </div>
          ))}
        </div>
      </div>

      {/* 2-Column Middle Grid Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 h-96 eb-glass border border-line rounded-[2px] p-6" />
        <div className="lg:col-span-5 h-96 eb-glass border border-line rounded-[2px] p-6" />
      </div>

      {/* Bottom Table Skeleton */}
      <div className="h-72 eb-glass border border-line rounded-[2px] p-6" />
    </div>
  );
}
