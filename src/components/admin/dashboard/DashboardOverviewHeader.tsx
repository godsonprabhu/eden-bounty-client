"use client";

import React from "react";
import { Shield, RotateCw, Clock, Inbox, AlertCircle } from "lucide-react";
import { AdminUser } from "@/types/admin";

interface DashboardOverviewHeaderProps {
  user: AdminUser | null;
  todayCount: number;
  unassignedCount: number;
  onRefresh: () => Promise<void>;
  isRefreshing: boolean;
  lastUpdated: Date | null;
}

export function DashboardOverviewHeader({
  user,
  todayCount,
  unassignedCount,
  onRefresh,
  isRefreshing,
  lastUpdated,
}: DashboardOverviewHeaderProps) {
  const isSuperAdmin = user?.roles.includes("SUPER_ADMIN");

  const formattedTime = lastUpdated
    ? lastUpdated.toLocaleTimeString("en-GB", {
        timeZone: "UTC",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }) + " UTC"
    : "Syncing...";

  return (
    <div className="p-6 rounded-[2px] border border-line eb-glass shadow-xs">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div>
          {/* Institutional Badge */}
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-brand-soft text-brand text-[10px] font-mono uppercase tracking-wider font-semibold">
              <Shield className="h-3 w-3" />
              <span>Central Operations Console</span>
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] border border-line-strong bg-panel-2 text-[10px] font-mono uppercase tracking-wider text-ink-muted">
              {isSuperAdmin ? "Super Admin Authority" : "Operations Admin Authority"}
            </span>
          </div>

          <h1 className="eb-display text-[1.9rem] text-ink sm:text-[2.4rem]">
            Operations Overview
          </h1>
          <p className="mt-1 text-xs sm:text-sm font-body text-ink-subtle">
            Logged in as{" "}
            <span className="font-mono text-ink font-medium">
              {user?.email}
            </span>{" "}
            • Real-time pipeline aggregation across all commercial divisions.
          </p>
        </div>

        {/* Action & Status Bar */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Today's Intake Pill */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-[2px] border border-line bg-panel-2">
            <Clock className="h-3.5 w-3.5 text-brand" />
            <div className="text-left">
              <span className="block text-[9px] font-mono uppercase tracking-wider text-ink-subtle">
                Today (UTC)
              </span>
              <span className="block text-xs font-mono font-bold text-ink">
                +{todayCount} new
              </span>
            </div>
          </div>

          {/* Unassigned Triage Pill */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-[2px] border border-line bg-panel-2">
            {unassignedCount > 0 ? (
              <AlertCircle className="h-3.5 w-3.5 text-[#D97706] dark:text-[#F59E0B]" />
            ) : (
              <Inbox className="h-3.5 w-3.5 text-[#10B981]" />
            )}
            <div className="text-left">
              <span className="block text-[9px] font-mono uppercase tracking-wider text-ink-subtle">
                Unassigned Triage
              </span>
              <span className="block text-xs font-mono font-bold text-ink">
                {unassignedCount} pending
              </span>
            </div>
          </div>

          {/* Refresh Action Button */}
          <button
            onClick={() => onRefresh()}
            disabled={isRefreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-[2px] border border-line-strong bg-panel text-xs font-heading font-semibold text-ink hover:bg-panel-2 hover:border-brand transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs"
            title={`Last updated at ${formattedTime}`}
          >
            <RotateCw
              className={`h-3.5 w-3.5 text-brand  ${
                isRefreshing ? "animate-spin" : ""
              }`}
            />
            <span>{isRefreshing ? "Syncing..." : "Refresh"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
