"use client";

import React from "react";
import { SearchX, Inbox, X } from "lucide-react";

interface EnquiryEmptyStateProps {
  hasFilters: boolean;
  onClearFilters: () => void;
}

export function EnquiryEmptyState({
  hasFilters,
  onClearFilters,
}: EnquiryEmptyStateProps) {
  return (
    <div className="p-8 sm:p-12 text-center rounded-[2px] border border-dashed border-line-strong eb-glass shadow-2xs">
      <div className="h-12 w-12 rounded-[2px] bg-panel-2 flex items-center justify-center mx-auto mb-3 border border-line">
        {hasFilters ? (
          <SearchX className="h-6 w-6 text-ink-subtle" />
        ) : (
          <Inbox className="h-6 w-6 text-ink-subtle" />
        )}
      </div>

      <h3 className="text-sm font-heading font-bold text-ink">
        {hasFilters ? "No matching enquiries found" : "No commercial enquiries registered"}
      </h3>

      <p className="mt-1 text-xs font-body text-ink-subtle max-w-sm mx-auto">
        {hasFilters
          ? "No enquiry records match your active search terms, division, status, or date range filters."
          : "The commercial enquiry database repository currently contains zero enquiry records."}
      </p>

      {hasFilters && (
        <div className="mt-4">
          <button
            type="button"
            onClick={onClearFilters}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] text-xs font-heading font-medium text-brand bg-brand-soft hover:bg-brand-soft dark:hover:bg-[#003C47] border border-brand/40 transition-colors cursor-pointer"
          >
            <X className="h-3.5 w-3.5" />
            <span>Reset Search & Filters</span>
          </button>
        </div>
      )}
    </div>
  );
}
