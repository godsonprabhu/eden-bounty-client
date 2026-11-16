"use client";

import React from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

interface EnquiryPaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  limit: number;
  onPageChange: (page: number) => void;
  onLimitChange: (limit: number) => void;
  isLoading: boolean;
}

export function EnquiryPagination({
  currentPage,
  totalPages,
  totalItems,
  limit,
  onPageChange,
  onLimitChange,
  isLoading,
}: EnquiryPaginationProps) {
  if (totalItems === 0) return null;

  const startItem = (currentPage - 1) * limit + 1;
  const endItem = Math.min(currentPage * limit, totalItems);

  // Generate visible page numbers
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);
      if (currentPage > 3) {
        pages.push("...");
      }
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }
      if (currentPage < totalPages - 2) {
        pages.push("...");
      }
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-[2px] border border-line eb-glass shadow-2xs">
      {/* Range Indicator & Limit Selector */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-body text-ink-subtle">
          Showing <span className="font-mono font-semibold text-ink">{startItem}</span> to{" "}
          <span className="font-mono font-semibold text-ink">{endItem}</span> of{" "}
          <span className="font-mono font-semibold text-ink">{totalItems}</span> entries
        </span>

        <div className="flex items-center gap-1.5 pl-3 border-l border-line">
          <label htmlFor="pagination-limit" className="text-xs font-body text-ink-subtle">
            Per page:
          </label>
          <select
            id="pagination-limit"
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            disabled={isLoading}
            className="px-2 py-1 rounded-[2px] text-xs font-mono border border-line-strong bg-panel-2 text-ink focus:outline-none focus:ring-1 focus:ring-brand cursor-pointer"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </div>
      </div>

      {/* Pagination Controls */}
      <div className="flex items-center gap-1 self-center sm:self-auto">
        {/* First Page */}
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={currentPage <= 1 || isLoading}
          aria-label="First page"
          className="p-1.5 rounded-[2px] border border-line-strong bg-panel-2 text-ink-subtle hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          <ChevronsLeft className="h-3.5 w-3.5" />
        </button>

        {/* Previous Page */}
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1 || isLoading}
          aria-label="Previous page"
          className="p-1.5 rounded-[2px] border border-line-strong bg-panel-2 text-ink-subtle hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>

        {/* Page Numbers */}
        <div className="flex items-center gap-1 px-1">
          {getPageNumbers().map((page, idx) => {
            if (typeof page === "string") {
              return (
                <span
                  key={`ellipsis-${idx}`}
                  className="px-1.5 text-xs font-mono text-ink-subtle"
                >
                  ...
                </span>
              );
            }

            const isActive = page === currentPage;
            return (
              <button
                key={page}
                type="button"
                onClick={() => onPageChange(page)}
                disabled={isLoading}
                aria-label={`Page ${page}`}
                aria-current={isActive ? "page" : undefined}
                className={`min-w-[28px] h-7 px-2 rounded-[2px] text-xs font-mono transition-colors cursor-pointer ${
                  isActive
                    ? "bg-brand  text-brand-ink dark:text-[#000000] font-bold"
                    : "border border-line-strong  bg-panel-2  text-ink-subtle  hover:text-ink "
                }`}
              >
                {page}
              </button>
            );
          })}
        </div>

        {/* Next Page */}
        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages || isLoading}
          aria-label="Next page"
          className="p-1.5 rounded-[2px] border border-line-strong bg-panel-2 text-ink-subtle hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>

        {/* Last Page */}
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages || isLoading}
          aria-label="Last page"
          className="p-1.5 rounded-[2px] border border-line-strong bg-panel-2 text-ink-subtle hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          <ChevronsRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
