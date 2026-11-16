"use client";

import React from "react";

export function EnquiryDossierSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header Skeleton */}
      <div className="space-y-2">
        <div className="h-4 w-48 bg-line rounded-[2px]" />
        <div className="p-6 rounded-[2px] border border-line eb-glass space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="h-7 w-64 bg-line rounded-[2px]" />
              <div className="h-4 w-96 bg-line rounded-[2px]" />
            </div>
            <div className="flex items-center gap-3">
              <div className="h-8 w-28 bg-line rounded-[2px]" />
              <div className="h-8 w-28 bg-line rounded-[2px]" />
            </div>
          </div>
        </div>
      </div>

      {/* Grid Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Main Column (8/12) */}
        <div className="lg:col-span-8 space-y-6">
          <div className="p-6 rounded-[2px] border border-line eb-glass space-y-4">
            <div className="h-5 w-48 bg-line rounded-[2px]" />
            <div className="grid grid-cols-2 gap-4">
              <div className="h-16 bg-panel-2 rounded-[2px]" />
              <div className="h-16 bg-panel-2 rounded-[2px]" />
            </div>
            <div className="h-32 bg-panel-2 rounded-[2px]" />
          </div>

          <div className="p-6 rounded-[2px] border border-line eb-glass space-y-4">
            <div className="h-5 w-56 bg-line rounded-[2px]" />
            <div className="space-y-4 pl-6">
              <div className="h-20 bg-panel-2 rounded-[2px]" />
              <div className="h-20 bg-panel-2 rounded-[2px]" />
            </div>
          </div>
        </div>

        {/* Side Column (4/12) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="p-5 rounded-[2px] border border-line eb-glass space-y-3">
            <div className="h-5 w-40 bg-line rounded-[2px]" />
            <div className="h-10 bg-panel-2 rounded-[2px]" />
            <div className="h-10 bg-panel-2 rounded-[2px]" />
            <div className="h-10 bg-panel-2 rounded-[2px]" />
          </div>

          <div className="p-5 rounded-[2px] border border-line eb-glass space-y-3">
            <div className="h-5 w-36 bg-line rounded-[2px]" />
            <div className="h-24 bg-panel-2 rounded-[2px]" />
          </div>
        </div>
      </div>
    </div>
  );
}
