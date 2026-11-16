"use client";

import React from "react";
import { DivisionMetricItem } from "@/types/admin";
import { allDivisions } from "@/data/divisions";
import { Briefcase } from "lucide-react";

interface DivisionDistributionCardProps {
  divisions: DivisionMetricItem[];
  totalEnquiries: number;
}

export function DivisionDistributionCard({
  divisions,
  totalEnquiries,
}: DivisionDistributionCardProps) {
  // Sort divisions by official code ascending (EB-DIV-01 to EB-DIV-10)
  // Ensure duplicate building-promotions is excluded if present
  const sortedDivisions = [...divisions]
    .filter((d) => d.division_id !== "building-promotions")
    .sort((a, b) => a.code.localeCompare(b.code));

  const INACTIVE_DIVISION_IDS = ["lubricants", "shisha-tobacco-trading", "axe-oil"];

  const activeCount = sortedDivisions.filter(
    (d) => d.is_active !== false && !INACTIVE_DIVISION_IDS.includes(d.division_id)
  ).length;

  return (
    <div className="p-5 sm:p-6 rounded-[2px] border border-line eb-glass flex flex-col justify-between h-full">
      <div>
        {/* Card Header */}
        <div className="flex items-center justify-between gap-3 mb-5 pb-3 border-b border-line">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-[2px] bg-brand-soft flex items-center justify-center shrink-0 border border-brand/40">
              <Briefcase className="h-4 w-4 text-brand" />
            </div>
            <div>
              <h2 className="text-sm font-heading font-bold text-ink">
                Service Volume Distribution
              </h2>
              <p className="text-[11px] font-body text-ink-subtle">
                Enquiry allocation across all commercial services
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-ink-subtle px-2 py-0.5 rounded-[2px] bg-panel-2">
            {activeCount || 6} Services Active
          </span>
        </div>

        {/* Division Breakdown List */}
        <div className="space-y-3.5">
          {sortedDivisions.map((div) => {
            const percentage =
              totalEnquiries > 0 ? Math.round((div.count / totalEnquiries) * 100) : 0;
            const isInactive = div.is_active === false || INACTIVE_DIVISION_IDS.includes(div.division_id);
            const divisionMeta = allDivisions.find((d) => d.id === div.division_id);
            const displayName = divisionMeta ? divisionMeta.name : div.name;

            return (
              <div key={div.division_id} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="px-1.5 py-0.5 rounded-[2px] bg-panel-2 text-[10px] font-mono text-ink-muted shrink-0 border border-line-strong">
                      {div.code}
                    </span>
                    <span className="font-heading font-semibold text-ink truncate">
                      {displayName}
                      {isInactive && (
                        <span className="ml-1.5 text-[9px] font-mono text-ink-subtle uppercase tracking-wider">
                          (Historical)
                        </span>
                      )}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <span className="font-mono text-xs font-bold text-ink">
                      {div.count}
                    </span>
                    <span className="text-[10px] font-mono text-ink-subtle w-8 text-right">
                      {percentage}%
                    </span>
                  </div>
                </div>

                {/* Accessible Visual Distribution Bar */}
                <div className="h-1.5 w-full bg-panel-2 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(percentage, div.count > 0 ? 3 : 0)}%` }}
                    role="progressbar"
                    aria-valuenow={percentage}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${displayName} enquiry share`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer Info Notice */}
      <div className="mt-5 pt-3 border-t border-line text-[10px] font-mono text-ink-subtle flex items-center justify-between">
        <span>Includes all non-soft-deleted enquiries</span>
        <span>Shah Alam Operations</span>
      </div>
    </div>
  );
}
