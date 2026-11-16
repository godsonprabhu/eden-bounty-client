"use client";

import React from "react";
import {
  Layers,
  Inbox,
  FileSearch,
  UserCheck,
  MessageSquare,
  FileCheck2,
  CheckCircle2,
  XCircle,
  Archive,
} from "lucide-react";

interface OverviewMetricsGridProps {
  totalEnquiries: number;
  byStatus: Record<string, number>;
}

interface StatusConfig {
  key: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  accentColor: string;
  darkAccentColor: string;
  bgLight: string;
  bgDark: string;
}

const STATUS_CONFIGS: StatusConfig[] = [
  {
    key: "NEW",
    label: "New Intake",
    description: "Initial client submissions awaiting triage",
    icon: Inbox,
    accentColor: "#0284C7",
    darkAccentColor: "#38BDF8",
    bgLight: "bg-brand-soft",
    bgDark: "dark:bg-[#082F49]/40",
  },
  {
    key: "UNDER_REVIEW",
    label: "Under Review",
    description: "Commercial specifications assessment",
    icon: FileSearch,
    accentColor: "#D97706",
    darkAccentColor: "#F59E0B",
    bgLight: "bg-[#FEF3C7]",
    bgDark: "dark:bg-[#451A03]/40",
  },
  {
    key: "ASSIGNED",
    label: "Assigned",
    description: "Routed to central operations desk",
    icon: UserCheck,
    accentColor: "#4F46E5",
    darkAccentColor: "#818CF8",
    bgLight: "bg-[#EEF2FF]",
    bgDark: "dark:bg-[#1E1B4B]/40",
  },
  {
    key: "IN_COMMUNICATION",
    label: "In Communication",
    description: "Active institutional correspondence",
    icon: MessageSquare,
    accentColor: "#059669",
    darkAccentColor: "#10B981",
    bgLight: "bg-[#D1FAE5]",
    bgDark: "dark:bg-[#064E3B]/40",
  },
  {
    key: "QUOTATION_PENDING",
    label: "Quotation Pending",
    description: "Pricing and trade desk terms review",
    icon: FileCheck2,
    accentColor: "#7C3AED",
    darkAccentColor: "#A855F7",
    bgLight: "bg-[#F3E8FF]",
    bgDark: "dark:bg-[#3B0764]/40",
  },
  {
    key: "COMPLETED",
    label: "Completed",
    description: "Trade desk enquiry concluded",
    icon: CheckCircle2,
    accentColor: "#0D9488",
    darkAccentColor: "#2DD4BF",
    bgLight: "bg-[#CCFBF1]",
    bgDark: "dark:bg-[#134E4A]/40",
  },
  {
    key: "DECLINED",
    label: "Declined",
    description: "Submissions outside commercial scope",
    icon: XCircle,
    accentColor: "#E11D48",
    darkAccentColor: "#FB7185",
    bgLight: "bg-[#FFE4E6]",
    bgDark: "dark:bg-[#4C0519]/40",
  },
  {
    key: "ARCHIVED",
    label: "Archived",
    description: "Dormant or concluded historical records",
    icon: Archive,
    accentColor: "#475569",
    darkAccentColor: "#94A3B8",
    bgLight: "bg-panel-2",
    bgDark: "dark:bg-[#0F172A]/40",
  },
];

export function OverviewMetricsGrid({
  totalEnquiries,
  byStatus,
}: OverviewMetricsGridProps) {
  return (
    <div className="space-y-4">
      {/* Hero Metric & Status Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-mono uppercase tracking-wider text-ink-subtle">
          Enquiry Lifecycle Pipeline
        </h2>
        <span className="text-[11px] font-mono text-ink-subtle">
          8 Lifecycle Stages Tracked
        </span>
      </div>

      {/* Hero Total Card + 8 Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* Total Volume Hero Card */}
        <div className="col-span-2 md:col-span-3 lg:col-span-4 p-5 rounded-[2px] border border-line-strong eb-glass shadow-2xs relative overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-[2px] bg-brand-soft flex items-center justify-center shrink-0 border border-brand/40">
                <Layers className="h-6 w-6 text-brand" />
              </div>
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
                  Total Active Commercial Pipeline
                </span>
                <div className="text-2xl sm:text-3xl font-heading font-bold text-ink mt-0.5">
                  {totalEnquiries}
                  <span className="text-xs sm:text-sm font-body font-normal text-ink-subtle ml-2">
                    enquiries across all divisions
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono text-ink-subtle pt-2 sm:pt-0 border-t sm:border-t-0 border-line">
              <span>Direct PostgreSQL Aggregation</span>
              <span>•</span>
              <span className="text-brand font-medium">100% Verified</span>
            </div>
          </div>
        </div>

        {/* 8 Individual Lifecycle Status Cards */}
        {STATUS_CONFIGS.map((cfg) => {
          const count = byStatus[cfg.key] || 0;
          const Icon = cfg.icon;

          return (
            <div
              key={cfg.key}
              className="p-4 rounded-[2px] border border-line bg-panel hover:border-line-strong transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-ink-subtle truncate">
                    {cfg.label}
                  </span>
                  <div
                    className={`h-7 w-7 rounded-[2px] ${cfg.bgLight} ${cfg.bgDark} flex items-center justify-center shrink-0`}
                  >
                    <Icon className="h-3.5 w-3.5" style={{ color: cfg.accentColor }} />
                  </div>
                </div>

                <div className="text-2xl sm:text-3xl font-heading font-bold text-ink">
                  {count}
                </div>
              </div>

              <div className="mt-3 pt-2 border-t border-line">
                <p className="text-[11px] font-body text-ink-subtle line-clamp-1">
                  {cfg.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
