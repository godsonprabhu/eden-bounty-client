"use client";

import React from "react";
import { FolderArchive, RefreshCw } from "lucide-react";

interface EnquiryRepositoryHeaderProps {
  totalItems: number;
  isLoading: boolean;
  onRefresh: () => void;
}

export function EnquiryRepositoryHeader({
  totalItems,
  isLoading,
  onRefresh,
}: EnquiryRepositoryHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-line">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-[2px] bg-brand-soft flex items-center justify-center shrink-0 border border-brand/40">
          <FolderArchive className="h-5 w-5 text-brand" />
        </div>
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="eb-display text-[1.9rem] text-ink sm:text-[2.4rem]">
              Commercial Enquiries Repository
            </h1>
            <span className="inline-flex items-center px-2 py-0.5 rounded-[2px] text-xs font-mono font-semibold bg-panel-2 text-ink-muted border border-line-strong">
              {totalItems} {totalItems === 1 ? "record" : "records"}
            </span>
          </div>
          <p className="text-xs font-body text-ink-subtle mt-0.5">
            Central repository, cross-division triage, and lifecycle management for commercial RFQs
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-start sm:self-auto">
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          aria-label="Refresh commercial enquiries list"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] border border-line-strong bg-panel text-xs font-heading font-medium text-ink-muted hover:text-ink hover:border-ink-subtle transition-colors disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin text-brand " : ""}`} />
          <span>Refresh</span>
        </button>
      </div>
    </div>
  );
}
