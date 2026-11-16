"use client";

import React from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface DashboardErrorStateProps {
  error: string;
  onRetry: () => void;
}

export function DashboardErrorState({ error, onRetry }: DashboardErrorStateProps) {
  return (
    <div className="p-8 sm:p-12 rounded-[2px] border border-[#FCA5A5] dark:border-[#7F1D1D] bg-[#FEF2F2] dark:bg-[#1A0A0C] text-center max-w-2xl mx-auto my-12">
      <div className="h-12 w-12 rounded-[2px] bg-[#FEE2E2] dark:bg-[#2D0D11] flex items-center justify-center mx-auto mb-4 border border-[#F87171]">
        <AlertTriangle className="h-6 w-6 text-[#DC2626] dark:text-[#EF4444]" />
      </div>

      <h2 className="text-lg font-heading font-bold text-[#991B1B] dark:text-[#FCA5A5]">
        Unable to Load Dashboard Data
      </h2>

      <p className="mt-2 text-xs font-body text-[#B91C1C] dark:text-[#F87171] max-w-md mx-auto leading-relaxed">
        {error || "An unexpected error occurred while communicating with the administrative API service."}
      </p>

      <div className="mt-6">
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-[2px] bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-heading font-semibold transition-colors shadow-xs"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          <span>Retry Connection</span>
        </button>
      </div>
    </div>
  );
}
