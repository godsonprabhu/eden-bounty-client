"use client";

import React, { useEffect, useState } from "react";
import { Search, X, Calendar, User, Layers, Tag } from "lucide-react";
import { allDivisions } from "@/data/divisions";
import { AdminAssigneeSummary } from "@/types/admin";

export interface FilterState {
  search: string;
  divisionId: string;
  status: string;
  assignedAdminId: string;
  createdFrom: string;
  createdTo: string;
}

interface EnquiryFiltersBarProps {
  filters: FilterState;
  administrators: AdminAssigneeSummary[];
  onFilterChange: (newFilters: Partial<FilterState>) => void;
  onClearFilters: () => void;
  isLoading: boolean;
}

const LIFECYCLE_STATUSES = [
  { value: "NEW", label: "New Intake" },
  { value: "UNDER_REVIEW", label: "Under Review" },
  { value: "ASSIGNED", label: "Assigned" },
  { value: "IN_COMMUNICATION", label: "In Communication" },
  { value: "QUOTATION_PENDING", label: "Quotation Pending" },
  { value: "COMPLETED", label: "Completed" },
  { value: "DECLINED", label: "Declined" },
  { value: "ARCHIVED", label: "Archived" },
];

export function EnquiryFiltersBar({
  filters,
  administrators,
  onFilterChange,
  onClearFilters,
  isLoading,
}: EnquiryFiltersBarProps) {
  const [searchInput, setSearchInput] = useState(filters.search);
  const [prevFilterSearch, setPrevFilterSearch] = useState(filters.search);
  const [dateError, setDateError] = useState<string | null>(null);

  // Sync internal search input if parent filters.search changes externally (without effect setState)
  if (filters.search !== prevFilterSearch) {
    setPrevFilterSearch(filters.search);
    setSearchInput(filters.search);
  }

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== filters.search) {
        onFilterChange({ search: searchInput });
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput, filters.search, onFilterChange]);

  // Date range validation
  const handleDateFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    if (filters.createdTo && val && val > filters.createdTo) {
      setDateError("Start date cannot be later than end date.");
      return;
    }
    setDateError(null);
    onFilterChange({ createdFrom: val });
  };

  const handleDateToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    if (filters.createdFrom && val && filters.createdFrom > val) {
      setDateError("End date cannot be earlier than start date.");
      return;
    }
    setDateError(null);
    onFilterChange({ createdTo: val });
  };

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.divisionId ||
      filters.status ||
      filters.assignedAdminId ||
      filters.createdFrom ||
      filters.createdTo
  );

  const activeFiltersCount = [
    filters.search,
    filters.divisionId,
    filters.status,
    filters.assignedAdminId,
    filters.createdFrom || filters.createdTo,
  ].filter(Boolean).length;

  return (
    <div className="space-y-3 p-4 rounded-[2px] border border-line eb-glass shadow-2xs">
      {/* Search and Primary Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Search Input */}
        <div className="relative">
          <label htmlFor="enquiry-search" className="sr-only">
            Search enquiries
          </label>
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
            <Search className="h-4 w-4" />
          </div>
          <input
            id="enquiry-search"
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search ref #, company..."
            className="w-full pl-9 pr-8 py-2 rounded-[2px] text-xs font-body border border-line-strong bg-panel-2 text-ink placeholder-ink-subtle focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand transition-colors"
          />
          {searchInput && (
            <button
              type="button"
              onClick={() => {
                setSearchInput("");
                onFilterChange({ search: "" });
              }}
              aria-label="Clear search text"
              className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-ink-subtle hover:text-ink cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Service Selector */}
        <div className="relative">
          <label htmlFor="enquiry-division" className="sr-only">
            Commercial Service
          </label>
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
            <Layers className="h-3.5 w-3.5" />
          </div>
          <select
            id="enquiry-division"
            value={filters.divisionId}
            onChange={(e) => onFilterChange({ divisionId: e.target.value })}
            className="w-full pl-8 pr-8 py-2 rounded-[2px] text-xs font-body border border-line-strong bg-panel-2 text-ink focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand transition-colors cursor-pointer appearance-none"
          >
            <option value="">All Commercial Services ({allDivisions.length})</option>
            {/* Includes inactive divisions so historical enquiries stay filterable. */}
            {allDivisions.map((div) => (
              <option key={div.id} value={div.id}>
                {div.name} ({div.code}){div.active === false ? " — inactive" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Status Selector */}
        <div className="relative">
          <label htmlFor="enquiry-status" className="sr-only">
            Lifecycle Status
          </label>
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
            <Tag className="h-3.5 w-3.5" />
          </div>
          <select
            id="enquiry-status"
            value={filters.status}
            onChange={(e) => onFilterChange({ status: e.target.value })}
            className="w-full pl-8 pr-8 py-2 rounded-[2px] text-xs font-body border border-line-strong bg-panel-2 text-ink focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand transition-colors cursor-pointer appearance-none"
          >
            <option value="">All Lifecycle Statuses (8)</option>
            {LIFECYCLE_STATUSES.map((st) => (
              <option key={st.value} value={st.value}>
                {st.label}
              </option>
            ))}
          </select>
        </div>

        {/* Assignee Selector */}
        <div className="relative">
          <label htmlFor="enquiry-assignee" className="sr-only">
            Assigned Administrator
          </label>
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
            <User className="h-3.5 w-3.5" />
          </div>
          <select
            id="enquiry-assignee"
            value={filters.assignedAdminId}
            onChange={(e) => onFilterChange({ assignedAdminId: e.target.value })}
            className="w-full pl-8 pr-8 py-2 rounded-[2px] text-xs font-body border border-line-strong bg-panel-2 text-ink focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand transition-colors cursor-pointer appearance-none"
          >
            <option value="">All Assignees</option>
            <option value="unassigned">⚠️ Unassigned Only</option>
            {administrators.map((admin) => (
              <option key={admin.id} value={admin.id}>
                {admin.first_name} {admin.last_name} ({admin.job_title || admin.roles.join(", ")})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Date Range & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-line">
        {/* Date Range Inputs */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 text-[11px] font-heading font-medium text-ink-subtle">
            <Calendar className="h-3.5 w-3.5 text-brand" />
            <span>Submission Range (UTC):</span>
          </div>

          <div className="flex items-center gap-1.5">
            <input
              type="date"
              aria-label="Created from date (UTC)"
              value={filters.createdFrom}
              onChange={handleDateFromChange}
              className="px-2 py-1 rounded-[2px] text-xs font-mono border border-line-strong bg-panel-2 text-ink focus:outline-none focus:ring-1 focus:ring-brand transition-colors"
            />
            <span className="text-xs font-body text-ink-subtle">to</span>
            <input
              type="date"
              aria-label="Created to date (UTC)"
              value={filters.createdTo}
              onChange={handleDateToChange}
              className="px-2 py-1 rounded-[2px] text-xs font-mono border border-line-strong bg-panel-2 text-ink focus:outline-none focus:ring-1 focus:ring-brand transition-colors"
            />
          </div>

          {dateError && (
            <span className="text-[11px] font-body text-[#EF4444] dark:text-[#F87171] ml-2">
              {dateError}
            </span>
          )}
        </div>

        {/* Clear Filters CTA */}
        {hasActiveFilters && (
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <span className="text-[10px] font-mono text-brand bg-brand-soft px-2 py-0.5 rounded-[2px] border border-brand/40">
              {activeFiltersCount} active {activeFiltersCount === 1 ? "filter" : "filters"}
            </span>
            <button
              type="button"
              onClick={() => {
                setSearchInput("");
                setDateError(null);
                onClearFilters();
              }}
              disabled={isLoading}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[2px] text-xs font-heading font-medium text-[#EF4444] dark:text-[#F87171] hover:bg-[#FEE2E2] dark:hover:bg-[#450A0A]/40 transition-colors cursor-pointer"
            >
              <X className="h-3 w-3" />
              <span>Clear Filters</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
