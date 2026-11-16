"use client";

import React, { FormEvent, useCallback, useEffect, useState } from "react";
import { CalendarClock, Filter, RotateCcw, ShieldCheck } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { apiGetAuditLogs, AdminApiError } from "@/lib/admin-api";
import {
  AuditLogListItem,
  AuditLogListResponseData,
} from "@/types/admin";
import { StateEmpty, StateError, StatePermissionDenied, LoadingSpinner } from "@/components/ui/states";
import { sanitizeErrorMessage } from "@/components/ui/states/StateError";

interface AuditFilters {
  action: string;
  entityTable: string;
}

const PAGE_SIZE = 50;

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function SnapshotDetails({
  label,
  snapshot,
}: {
  label: string;
  snapshot: Record<string, unknown> | null;
}) {
  if (snapshot === null) {
    return <span className="text-ink-subtle">—</span>;
  }

  return (
    <details className="min-w-48 max-w-[28rem]">
      <summary className="cursor-pointer select-none text-xs font-heading font-semibold text-brand hover:underline">
        View {label}
      </summary>
      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-[2px] border border-line bg-panel-2 p-3 text-[11px] leading-relaxed text-ink-muted">
        {JSON.stringify(snapshot, null, 2)}
      </pre>
    </details>
  );
}

function AuditTable({ records }: { records: AuditLogListItem[] }) {
  return (
    <div className="overflow-x-auto rounded-[2px] border border-line eb-glass shadow-sm">
      <table className="w-full min-w-[1120px] border-collapse text-left">
        <thead className="bg-panel-2">
          <tr className="border-b border-line">
            {[
              "Timestamp",
              "Actor",
              "Action",
              "Entity / Table",
              "Entity ID",
              "IP Address",
              "Previous State",
              "New State",
            ].map((heading) => (
              <th
                key={heading}
                scope="col"
                className="whitespace-nowrap px-4 py-3 text-[10px] font-mono font-semibold uppercase tracking-wider text-ink-subtle"
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {records.map((record) => (
            <tr key={record.id} className="align-top hover:bg-panel-2">
              <td className="whitespace-nowrap px-4 py-3 text-xs text-ink-muted">
                <time dateTime={record.timestamp}>{formatTimestamp(record.timestamp)}</time>
              </td>
              <td className="max-w-52 px-4 py-3 text-xs text-ink">
                <div className="break-all">{record.actor_email || "System / unavailable"}</div>
                {record.actor_admin_id && (
                  <div className="mt-1 break-all font-mono text-[10px] text-ink-subtle">
                    {record.actor_admin_id}
                  </div>
                )}
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex rounded-[2px] border border-brand/40 bg-brand-soft px-2 py-1 font-mono text-[10px] font-semibold text-brand-hover">
                  {record.action}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-ink-muted">
                <div className="font-semibold text-ink">{record.entity_table}</div>
                <div className="mt-1 font-mono text-[10px] text-ink-subtle">#{record.id}</div>
              </td>
              <td className="max-w-56 break-all px-4 py-3 font-mono text-[10px] text-ink-muted">
                {record.entity_id}
              </td>
              <td className="whitespace-nowrap px-4 py-3 font-mono text-[11px] text-ink-muted">
                {record.ip_address || "—"}
              </td>
              <td className="px-4 py-3">
                <SnapshotDetails label="previous state" snapshot={record.old_state} />
              </td>
              <td className="px-4 py-3">
                <SnapshotDetails label="new state" snapshot={record.new_state} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminAuditPage() {
  const { hasRole } = useAdminAuth();
  const isSuperAdmin = hasRole("SUPER_ADMIN");

  const [page, setPage] = useState(1);
  const [draftFilters, setDraftFilters] = useState<AuditFilters>({ action: "", entityTable: "" });
  const [appliedFilters, setAppliedFilters] = useState<AuditFilters>({ action: "", entityTable: "" });
  const [response, setResponse] = useState<AuditLogListResponseData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | undefined>();
  const [retryKey, setRetryKey] = useState(0);

  const appliedAction = appliedFilters.action;
  const appliedEntityTable = appliedFilters.entityTable;

  useEffect(() => {
    if (!isSuperAdmin) return;

    const controller = new AbortController();
    const loadAuditLogs = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      setErrorStatus(undefined);

      try {
        const data = await apiGetAuditLogs(
          {
            page,
            limit: PAGE_SIZE,
            action: appliedAction || undefined,
            entity_table: appliedEntityTable || undefined,
          },
          { signal: controller.signal }
        );
        if (!controller.signal.aborted) setResponse(data);
      } catch (error: unknown) {
        if (controller.signal.aborted) return;
        if (error instanceof AdminApiError) {
          setErrorMessage(sanitizeErrorMessage(error.detail, error.status));
          setErrorStatus(error.status);
        } else {
          setErrorMessage(sanitizeErrorMessage(error));
          setErrorStatus(undefined);
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    };

    void loadAuditLogs();

    return () => controller.abort();
  }, [isSuperAdmin, page, appliedAction, appliedEntityTable, retryKey]);

  const handleApplyFilters = useCallback((event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextFilters = {
      action: draftFilters.action.trim(),
      entityTable: draftFilters.entityTable.trim(),
    };
    if (
      nextFilters.action === appliedFilters.action &&
      nextFilters.entityTable === appliedFilters.entityTable &&
      page === 1
    ) {
      return;
    }
    setAppliedFilters(nextFilters);
    setPage(1);
  }, [draftFilters, appliedFilters, page]);

  const handleResetFilters = useCallback(() => {
    if (!appliedFilters.action && !appliedFilters.entityTable && page === 1) {
      setDraftFilters({ action: "", entityTable: "" });
      return;
    }
    setDraftFilters({ action: "", entityTable: "" });
    setAppliedFilters({ action: "", entityTable: "" });
    setPage(1);
  }, [appliedFilters, page]);

  const handleRetry = useCallback(() => setRetryKey((key) => key + 1), []);
  const hasActiveFilters = Boolean(appliedFilters.action || appliedFilters.entityTable);
  const hasDraftChanges =
    draftFilters.action.trim() !== appliedFilters.action ||
    draftFilters.entityTable.trim() !== appliedFilters.entityTable;
  const pagination = response?.pagination;
  const totalItems = pagination?.total_items ?? 0;
  const totalPages = pagination?.total_pages ?? 1;

  if (!isSuperAdmin) {
    return (
      <div className="max-w-7xl mx-auto space-y-6">
        <StatePermissionDenied
          title="Audit Ledger Access Restricted"
          message="The audit ledger is available only to authorized SUPER_ADMIN users."
          requiredRole="SUPER_ADMIN"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 min-w-0">
      <header className="flex flex-col gap-3 border-b border-line pb-4 sm:flex-row sm:items-center">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[2px] border border-brand/40 bg-brand-soft">
          <ShieldCheck className="h-5 w-5 text-brand" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="eb-display text-[1.9rem] text-ink sm:text-[2.4rem]">
              Admin Audit Ledger
            </h1>
            {response && (
              <span className="rounded-[2px] border border-line-strong bg-panel-2 px-2 py-0.5 font-mono text-[11px] font-semibold text-ink-muted">
                {totalItems.toLocaleString()} {totalItems === 1 ? "record" : "records"}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-ink-subtle">
            Review recorded administrative actions and their associated context.
          </p>
        </div>
      </header>

      <form
        onSubmit={handleApplyFilters}
        className="grid grid-cols-1 gap-3 rounded-[2px] border border-line eb-glass p-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] lg:items-end"
        aria-label="Filter audit records"
      >
        <div className="min-w-0">
          <label htmlFor="audit-action-filter" className="mb-1.5 block text-[10px] font-mono font-semibold uppercase tracking-wider text-ink-subtle">
            Action (exact match)
          </label>
          <input
            id="audit-action-filter"
            value={draftFilters.action}
            onChange={(event) => setDraftFilters((current) => ({ ...current, action: event.target.value }))}
            maxLength={100}
            autoComplete="off"
            placeholder="For example, STATUS_CHANGED"
            className="min-h-10 w-full min-w-0 rounded-[2px] border border-line-strong bg-panel-2 px-3 text-xs text-ink dark:text-white placeholder:text-ink-subtle focus-visible:outline-2 focus-visible:outline-brand"
          />
        </div>
        <div className="min-w-0">
          <label htmlFor="audit-entity-filter" className="mb-1.5 block text-[10px] font-mono font-semibold uppercase tracking-wider text-ink-subtle">
            Entity / table (exact match)
          </label>
          <input
            id="audit-entity-filter"
            value={draftFilters.entityTable}
            onChange={(event) => setDraftFilters((current) => ({ ...current, entityTable: event.target.value }))}
            maxLength={50}
            autoComplete="off"
            placeholder="For example, enquiries"
            className="min-h-10 w-full min-w-0 rounded-[2px] border border-line-strong bg-panel-2 px-3 text-xs text-ink dark:text-white placeholder:text-ink-subtle focus-visible:outline-2 focus-visible:outline-brand"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !hasDraftChanges}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-[2px] bg-brand px-4 text-xs font-heading font-semibold uppercase tracking-wider text-brand-ink transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Filter className="h-3.5 w-3.5" />
          Apply filters
        </button>
        <button
          type="button"
          onClick={handleResetFilters}
          disabled={isLoading || (!hasActiveFilters && !draftFilters.action && !draftFilters.entityTable)}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-[2px] border border-line-strong px-4 text-xs font-heading font-semibold uppercase tracking-wider text-ink-muted transition-colors hover:bg-panel-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </button>
      </form>

      {isLoading ? (
        <div className="rounded-[2px] border border-line eb-glass py-16">
          <LoadingSpinner label="Loading audit records..." />
        </div>
      ) : errorMessage ? (
        <StateError
          title="Unable to Load Audit Records"
          message={errorMessage}
          statusCode={errorStatus}
          onRetry={handleRetry}
        />
      ) : response && response.items.length === 0 ? (
        <StateEmpty
          title={hasActiveFilters ? "No matching audit records" : "No audit records available"}
          description={hasActiveFilters ? "No records match the applied action and entity filters." : "The audit ledger currently contains no records."}
          isFiltered={hasActiveFilters}
          secondaryAction={hasActiveFilters ? { label: "Reset filters", onClick: handleResetFilters } : undefined}
        />
      ) : response ? (
        <>
          <section aria-label="Audit records" className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xs font-heading font-semibold uppercase tracking-wider text-ink-muted">
                Audit records
              </h2>
              <div className="inline-flex items-center gap-1.5 font-mono text-[10px] text-ink-subtle">
                <CalendarClock className="h-3.5 w-3.5" />
                <span>Newest first</span>
              </div>
            </div>
            <AuditTable records={response.items} />
          </section>

          <nav
            aria-label="Audit record pages"
            className="flex flex-col gap-3 rounded-[2px] border border-line eb-glass p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <p className="text-xs text-ink-subtle">
              Page <span className="font-mono font-semibold text-ink dark:text-white">{pagination?.page ?? page}</span> of{" "}
              <span className="font-mono font-semibold text-ink dark:text-white">{totalPages}</span>
              <span className="mx-2 text-line-strong">•</span>
              <span className="font-mono font-semibold text-ink dark:text-white">{totalItems.toLocaleString()}</span> total records
            </p>
            <div className="flex items-center gap-2 self-start sm:self-auto">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={isLoading || page <= 1}
                className="min-h-10 rounded-[2px] border border-line-strong px-4 text-xs font-heading font-semibold text-ink-muted hover:bg-panel-2 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                disabled={isLoading || page >= totalPages}
                className="min-h-10 rounded-[2px] border border-line-strong px-4 text-xs font-heading font-semibold text-ink-muted hover:bg-panel-2 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </nav>
        </>
      ) : null}
    </div>
  );
}
