"use client";

import React from "react";
import { ArrowRight, Clock, RefreshCw, UserCheck } from "lucide-react";
import { EnquiryStatusHistoryItem } from "@/types/admin";

interface StatusHistoryCardProps {
  statusHistory: EnquiryStatusHistoryItem[];
}

export function StatusHistoryCard({ statusHistory }: StatusHistoryCardProps) {
  return (
    <div className="rounded-[2px] border border-line eb-glass p-5 shadow-2xs space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-line">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
            <RefreshCw className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-xs font-heading font-bold uppercase tracking-wider text-ink">
              Status Progression History
            </h2>
            <p className="text-[11px] font-mono text-ink-subtle">
              Lifecycle audit records ({statusHistory.length})
            </p>
          </div>
        </div>
      </div>

      {statusHistory.length === 0 ? (
        <div className="text-center py-6 border border-dashed border-line rounded-[2px] text-xs font-mono text-ink-subtle">
          No status transitions recorded. Enquiry is in initial intake state.
        </div>
      ) : (
        <div className="space-y-3">
          {statusHistory.map((s) => {
            const formattedDate = new Date(s.created_at)
              .toISOString()
              .replace("T", " ")
              .replace(/\.\d{3}Z$/, " UTC");

            return (
              <div
                key={s.id}
                className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-2 text-xs font-mono"
              >
                {/* Transition Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2 py-0.5 rounded-[2px] bg-panel-2 text-ink-muted border border-line-strong">
                    {s.old_status}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 text-ink-subtle" />
                  <span className="px-2 py-0.5 rounded-[2px] bg-[#EFF6FF] dark:bg-[#1E3A8A] text-[#1D4ED8] dark:text-[#93C5FD] border border-[#BFDBFE] dark:border-[#3B82F6] font-medium">
                    {s.new_status}
                  </span>
                </div>

                {/* Change Reason */}
                {s.change_reason && (
                  <p className="text-ink-muted text-[11px] leading-relaxed">
                    {s.change_reason}
                  </p>
                )}

                {/* Actor & Timestamp */}
                <div className="pt-2 border-t border-line flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-subtle">
                  <div className="flex items-center gap-1.5">
                    <UserCheck className="h-3 w-3" />
                    <span>Changed by: {s.changed_by_admin?.name || "Operations Administrator"}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>{formattedDate}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
