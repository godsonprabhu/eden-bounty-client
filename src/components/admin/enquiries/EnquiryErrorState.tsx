"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface EnquiryErrorStateProps {
  message: string;
  onRetry: () => void;
}

export function EnquiryErrorState({ message, onRetry }: EnquiryErrorStateProps) {
  return (
    <div className="p-8 sm:p-12 text-center rounded-[2px] border border-[#FECDD3] dark:border-[#881337] bg-[#FFF1F2] dark:bg-[#1C0A0E] shadow-2xs">
      <div className="h-12 w-12 rounded-[2px] bg-[#FFE4E6] dark:bg-[#4C0519] flex items-center justify-center mx-auto mb-3 border border-[#FDA4AF] dark:border-[#9F1239]">
        <AlertTriangle className="h-6 w-6 text-[#E11D48] dark:text-[#FB7185]" />
      </div>

      <h3 className="text-sm font-heading font-bold text-[#9F1239] dark:text-[#FFE4E6]">
        Failed to load enquiries repository
      </h3>

      <p className="mt-1 text-xs font-mono text-[#BE123C] dark:text-[#FDA4AF] max-w-md mx-auto break-words">
        {message}
      </p>

      <div className="mt-4">
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] text-xs font-heading font-medium text-ink bg-[#E11D48] hover:bg-[#BE123C] transition-colors cursor-pointer shadow-2xs"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Retry Request</span>
        </button>
      </div>
    </div>
  );
}
