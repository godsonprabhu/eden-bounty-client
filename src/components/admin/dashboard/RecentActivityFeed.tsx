"use client";

import React from "react";
import { DashboardActivityItem } from "@/types/admin";
import {
  Activity,
  ArrowRightCircle,
  UserCheck,
  UserMinus,
  Clock,
  ShieldCheck,
} from "lucide-react";

interface RecentActivityFeedProps {
  activities: DashboardActivityItem[];
}

function getActivityIcon(eventType: string) {
  switch (eventType) {
    case "STATUS_CHANGED":
      return <ArrowRightCircle className="h-3.5 w-3.5 text-brand" />;
    case "ENQUIRY_ASSIGNED":
      return <UserCheck className="h-3.5 w-3.5 text-[#10B981]" />;
    case "ENQUIRY_UNASSIGNED":
      return <UserMinus className="h-3.5 w-3.5 text-[#F59E0B]" />;
    default:
      return <Activity className="h-3.5 w-3.5 text-[#8B5CF6]" />;
  }
}

export function RecentActivityFeed({ activities }: RecentActivityFeedProps) {
  return (
    <div className="p-5 sm:p-6 rounded-[2px] border border-line eb-glass flex flex-col justify-between h-full">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-5 pb-3 border-b border-line">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-[2px] bg-brand-soft flex items-center justify-center shrink-0 border border-brand/40">
              <Activity className="h-4 w-4 text-brand" />
            </div>
            <div>
              <h2 className="text-sm font-heading font-bold text-ink">
                Operational Activity Summary
              </h2>
              <p className="text-[11px] font-body text-ink-subtle">
                Real-time operational audit log events (Privacy-Safe)
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-brand px-2 py-0.5 rounded-[2px] bg-brand-soft font-semibold">
            Audit Stream
          </span>
        </div>

        {/* Activity Items */}
        {activities.length === 0 ? (
          <div className="py-8 text-center border border-dashed border-line-strong rounded-[2px] bg-panel-2">
            <p className="text-xs font-body text-ink-subtle">
              No operational events recorded in the audit log yet.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {activities.map((act) => {
              const actDate = new Date(act.timestamp);
              const formattedDate = actDate.toLocaleDateString("en-GB", {
                timeZone: "UTC",
                month: "short",
                day: "2-digit",
              });
              const formattedTime = actDate.toLocaleTimeString("en-GB", {
                timeZone: "UTC",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <div
                  key={act.id}
                  className="p-3 rounded-[2px] border border-line bg-panel-2 hover:border-line-strong transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 shrink-0">
                        {getActivityIcon(act.event_type)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-ink">
                            {act.reference_number}
                          </span>
                          <span className="text-[10px] font-body text-ink-subtle">
                            • {act.division_name}
                          </span>
                        </div>
                        <p className="mt-0.5 text-xs font-body text-ink-muted">
                          {act.description}
                        </p>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-[10px] font-mono text-ink-subtle block">
                        {formattedDate} {formattedTime} UTC
                      </span>
                      <span className="text-[9px] font-body text-ink-muted block mt-0.5">
                        by {act.actor_name}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Info Notice */}
      <div className="mt-5 pt-3 border-t border-line text-[10px] font-mono text-ink-subtle flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="h-3 w-3 text-[#10B981]" />
          <span>Internal notes and customer PII strictly excluded</span>
        </div>
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span>Latest 10 Events</span>
        </div>
      </div>
    </div>
  );
}
