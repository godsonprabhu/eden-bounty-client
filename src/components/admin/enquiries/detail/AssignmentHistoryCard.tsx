"use client";

import React from "react";
import { ArrowRight, Clock, UserCheck, Users } from "lucide-react";
import { EnquiryAssignmentHistoryItem } from "@/types/admin";

interface AssignmentHistoryCardProps {
  assignments: EnquiryAssignmentHistoryItem[];
}

export function AssignmentHistoryCard({ assignments }: AssignmentHistoryCardProps) {
  return (
    <div className="rounded-[2px] border border-line eb-glass p-5 shadow-2xs space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-line">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
            <Users className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-xs font-heading font-bold uppercase tracking-wider text-ink">
              Assignment History
            </h2>
            <p className="text-[11px] font-mono text-ink-subtle">
              Record of administrative routing ({assignments.length})
            </p>
          </div>
        </div>
      </div>

      {assignments.length === 0 ? (
        <div className="text-center py-6 border border-dashed border-line rounded-[2px] text-xs font-mono text-ink-subtle">
          No reassignments recorded. Enquiry remains in original assignment state.
        </div>
      ) : (
        <div className="space-y-3">
          {assignments.map((a) => {
            const formattedDate = new Date(a.assigned_at)
              .toISOString()
              .replace("T", " ")
              .replace(/\.\d{3}Z$/, " UTC");

            return (
              <div
                key={a.id}
                className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-2 text-xs font-mono"
              >
                {/* Transfer Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2 py-0.5 rounded-[2px] bg-panel-2 text-ink-muted border border-line-strong">
                    {a.previous_admin?.name || "Unassigned"}
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 text-ink-subtle" />
                  <span className="px-2 py-0.5 rounded-[2px] bg-brand-soft text-brand border border-brand/40 font-medium">
                    {a.new_admin?.name || "Unassigned"}
                  </span>
                </div>

                {/* Assignment Rationale */}
                {a.assignment_rationale && (
                  <p className="text-ink-muted text-[11px] leading-relaxed">
                    {a.assignment_rationale}
                  </p>
                )}

                {/* Actor & Timestamp */}
                <div className="pt-2 border-t border-line flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-subtle">
                  <div className="flex items-center gap-1.5">
                    <UserCheck className="h-3 w-3" />
                    <span>Assigned by: {a.assigned_by_admin?.name || "Operations Lead"}</span>
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
