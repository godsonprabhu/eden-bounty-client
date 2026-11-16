"use client";

import React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";

interface EnquiryDossierErrorProps {
  message: string;
  onRetry: () => void;
}

export function EnquiryDossierError({ message, onRetry }: EnquiryDossierErrorProps) {
  return (
    <div className="max-w-2xl mx-auto py-12 text-center space-y-6">
      <div className="p-8 sm:p-12 rounded-[2px] border border-[#FECACA] dark:border-[#7F1D1D] bg-[#FEF2F2] dark:bg-[#1A0B0B] shadow-2xs space-y-4">
        <div className="h-14 w-14 rounded-[2px] bg-[#FEE2E2] dark:bg-[#2C1111] flex items-center justify-center mx-auto border border-[#FECACA] dark:border-[#991B1B]">
          <AlertTriangle className="h-7 w-7 text-[#DC2626] dark:text-[#EF4444]" />
        </div>

        <h1 className="text-lg sm:text-xl font-heading font-bold text-[#991B1B] dark:text-[#F87171]">
          Failed to Load Enquiry Dossier
        </h1>

        <p className="text-xs font-mono text-[#B91C1C] dark:text-[#FCA5A5] max-w-md mx-auto leading-relaxed">
          {message}
        </p>

        <div className="pt-4 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[2px] text-xs font-heading font-medium text-ink bg-[#DC2626] hover:bg-[#B91C1C] transition-colors cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry Loading</span>
          </button>

          <Link
            href="/admin/enquiries"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[2px] text-xs font-heading font-medium text-ink-muted bg-panel border border-line-strong hover:bg-panel-2 transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Return to Repository</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
