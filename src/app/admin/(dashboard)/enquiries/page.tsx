"use client";

import React, { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { apiGetAdministrators, apiSearchEnquiries } from "@/lib/admin-api";
import { AdminAssigneeSummary, EnquiryListItem, EnquirySearchRequestBody } from "@/types/admin";
import { EnquiryRepositoryHeader } from "@/components/admin/enquiries/EnquiryRepositoryHeader";
import { EnquiryFiltersBar, FilterState } from "@/components/admin/enquiries/EnquiryFiltersBar";
import { EnquiryTable } from "@/components/admin/enquiries/EnquiryTable";
import { EnquiryPagination } from "@/components/admin/enquiries/EnquiryPagination";
import { EnquiryTableSkeleton } from "@/components/admin/enquiries/EnquiryTableSkeleton";
import { EnquiryEmptyState } from "@/components/admin/enquiries/EnquiryEmptyState";
import { EnquiryErrorState } from "@/components/admin/enquiries/EnquiryErrorState";
import { sanitizeErrorMessage } from "@/components/ui/states/StateError";

export default function AdminEnquiriesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const { csrfToken } = useAdminAuth();

  // URL Query Parameters initialization (SEC-01: search is strictly excluded from URL)
  const initialPage = Number(searchParams.get("page")) || 1;
  const initialLimit = Number(searchParams.get("limit")) || 25;
  const initialDivision = searchParams.get("division_id") || "";
  const initialStatus = searchParams.get("status") || "";
  const initialAssignee = searchParams.get("assigned_admin_id") || "";
  const initialCreatedFrom = searchParams.get("created_from") || "";
  const initialCreatedTo = searchParams.get("created_to") || "";
  const initialSortBy = (searchParams.get("sort_by") as "created_at" | "reference_number" | "company_name" | "status") || "created_at";
  const initialSortOrder = (searchParams.get("sort_order") as "asc" | "desc") || "desc";

  // State (search resides exclusively in React memory)
  const [items, setItems] = useState<EnquiryListItem[]>([]);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [currentPage, setCurrentPage] = useState<number>(initialPage);
  const [limit, setLimit] = useState<number>(initialLimit);
  const [sortBy, setSortBy] = useState<"created_at" | "reference_number" | "company_name" | "status">(initialSortBy);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">(initialSortOrder);

  const [filters, setFilters] = useState<FilterState>({
    search: "", // SEC-01: React in-memory only — never loaded from URL
    divisionId: initialDivision,
    status: initialStatus,
    assignedAdminId: initialAssignee,
    createdFrom: initialCreatedFrom,
    createdTo: initialCreatedTo,
  });

  const [administrators, setAdministrators] = useState<AdminAssigneeSummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  // Sync state to URL without polluting browser history (router.replace)
  // SEC-01 Privacy Invariant: search terms are NEVER written to the browser URL!
  const syncUrlParams = useCallback(
    (
      pg: number,
      lim: number,
      flts: FilterState,
      sort: string,
      order: string
    ) => {
      const params = new URLSearchParams();
      if (pg > 1) params.set("page", pg.toString());
      if (lim !== 25) params.set("limit", lim.toString());
      // Explicitly omit flts.search from URL parameters
      if (flts.divisionId) params.set("division_id", flts.divisionId);
      if (flts.status) params.set("status", flts.status);
      if (flts.assignedAdminId) params.set("assigned_admin_id", flts.assignedAdminId);
      if (flts.createdFrom) params.set("created_from", flts.createdFrom);
      if (flts.createdTo) params.set("created_to", flts.createdTo);
      if (sort !== "created_at") params.set("sort_by", sort);
      if (order !== "desc") params.set("sort_order", order);

      const qs = params.toString();
      startTransition(() => {
        router.replace(`/admin/enquiries${qs ? `?${qs}` : ""}`, { scroll: false });
      });
    },
    [router]
  );

  // Load active administrators for filter dropdown
  useEffect(() => {
    let isMounted = true;
    async function loadAdmins() {
      try {
        const admins = await apiGetAdministrators();
        if (isMounted) {
          setAdministrators(admins);
        }
      } catch (err) {
        console.error("Failed to load administrators directory for filter:", err);
      }
    }
    loadAdmins();
    return () => {
      isMounted = false;
    };
  }, []);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch enquiries repository from backend on dependency changes
  // SEC-01: Uses authenticated POST /api/v1/admin/rfqs/search with encrypted JSON body
  useEffect(() => {
    let isMounted = true;

    // Await CSRF token hydration from AdminAuthContext before firing POST query
    if (!csrfToken) {
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    async function loadData() {
      const searchBody: EnquirySearchRequestBody = {
        page: currentPage,
        limit,
        sort_by: sortBy,
        sort_order: sortOrder,
      };

      if (filters.search) searchBody.search = filters.search.trim();
      if (filters.divisionId) searchBody.division_id = filters.divisionId;
      if (filters.status) searchBody.status = filters.status;
      if (filters.assignedAdminId) searchBody.assigned_admin_id = filters.assignedAdminId;
      if (filters.createdFrom) {
        searchBody.created_from = `${filters.createdFrom}T00:00:00Z`;
      }
      if (filters.createdTo) {
        searchBody.created_to = `${filters.createdTo}T23:59:59.999Z`;
      }

      try {
        const data = await apiSearchEnquiries(searchBody, csrfToken, { signal: controller.signal });
        if (isMounted) {
          setItems(data.items);
          setTotalItems(data.pagination.total_items);
          setTotalPages(data.pagination.total_pages || 1);
          setErrorMessage(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (controller.signal.aborted) return;
        if (isMounted) {
          const rawMsg = err instanceof Error ? err.message : "Failed to load enquiries";
          setErrorMessage(sanitizeErrorMessage(rawMsg));
          setItems([]);
          setIsLoading(false);
        }
      }
    }

    loadData();
    syncUrlParams(currentPage, limit, filters, sortBy, sortOrder);

    return () => {
      isMounted = false;
    };
  }, [currentPage, limit, sortBy, sortOrder, filters, refreshKey, csrfToken, syncUrlParams]);

  // Refresh trigger handler
  const handleRefresh = () => {
    setIsLoading(true);
    setRefreshKey((k) => k + 1);
  };

  // Filter change handler (resets page to 1)
  const handleFilterChange = (newFilters: Partial<FilterState>) => {
    setIsLoading(true);
    setFilters((prev) => ({ ...prev, ...newFilters }));
    setCurrentPage(1);
  };

  // Clear all filters handler (resets to defaults)
  const handleClearFilters = () => {
    setIsLoading(true);
    setFilters({
      search: "",
      divisionId: "",
      status: "",
      assignedAdminId: "",
      createdFrom: "",
      createdTo: "",
    });
    setCurrentPage(1);
  };

  // Sorting change handler
  const handleSortChange = (column: "created_at" | "reference_number" | "company_name" | "status") => {
    setIsLoading(true);
    if (sortBy === column) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortOrder("desc");
    }
    setCurrentPage(1);
  };

  // Page change handler
  const handlePageChange = (newPage: number) => {
    setIsLoading(true);
    setCurrentPage(newPage);
  };

  // Limit change handler
  const handleLimitChange = (newLimit: number) => {
    setIsLoading(true);
    setLimit(newLimit);
    setCurrentPage(1);
  };

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.divisionId ||
      filters.status ||
      filters.assignedAdminId ||
      filters.createdFrom ||
      filters.createdTo
  );

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {/* Page Header */}
      <EnquiryRepositoryHeader
        totalItems={totalItems}
        isLoading={isLoading}
        onRefresh={handleRefresh}
      />

      {/* Filter and Search Bar */}
      <EnquiryFiltersBar
        filters={filters}
        administrators={administrators}
        onFilterChange={handleFilterChange}
        onClearFilters={handleClearFilters}
        isLoading={isLoading}
      />

      {/* Main Content Area: Table / Loading / Error / Empty */}
      {errorMessage ? (
        <EnquiryErrorState message={errorMessage} onRetry={handleRefresh} />
      ) : isLoading && items.length === 0 ? (
        <EnquiryTableSkeleton />
      ) : items.length === 0 ? (
        <EnquiryEmptyState
          hasFilters={hasActiveFilters}
          onClearFilters={handleClearFilters}
        />
      ) : (
        <div className="space-y-4">
          <EnquiryTable
            items={items}
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSortChange={handleSortChange}
          />

          {/* Pagination Controls */}
          <EnquiryPagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={totalItems}
            limit={limit}
            onPageChange={handlePageChange}
            onLimitChange={handleLimitChange}
            isLoading={isLoading}
          />
        </div>
      )}
    </div>
  );
}
