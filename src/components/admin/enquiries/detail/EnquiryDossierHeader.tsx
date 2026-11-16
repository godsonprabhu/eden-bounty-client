"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Clock,
  Copy,
  RefreshCw,
  ShieldAlert,
  User,
  UserCheck,
} from "lucide-react";
import { EnquiryDetailResponseData } from "@/types/admin";

interface EnquiryDossierHeaderProps {
  dossier: EnquiryDetailResponseData;
  onRefresh: () => void;
  isLoading: boolean;
  onOpenAssignModal?: () => void;
  onOpenStatusModal?: () => void;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; bgLight: string; textLight: string; borderLight: string; bgDark: string; textDark: string; borderDark: string }
> = {
  NEW: {
    label: "New Intake",
    bgLight: "bg-[#EFF6FF]",
    textLight: "text-[#1D4ED8]",
    borderLight: "border-[#BFDBFE]",
    bgDark: "dark:bg-[#1E293B]",
    textDark: "dark:text-[#60A5FA]",
    borderDark: "dark:border-[#3B82F6]/40",
  },
  UNDER_REVIEW: {
    label: "Under Review",
    bgLight: "bg-[#FFFBEB]",
    textLight: "text-[#B45309]",
    borderLight: "border-[#FDE68A]",
    bgDark: "dark:bg-[#2D2312]",
    textDark: "dark:text-[#FBBF24]",
    borderDark: "dark:border-[#F59E0B]/40",
  },
  ASSIGNED: {
    label: "Assigned",
    bgLight: "bg-[#EEF2FF]",
    textLight: "text-[#4338CA]",
    borderLight: "border-[#C7D2FE]",
    bgDark: "dark:bg-[#1E1B4B]/40",
    textDark: "dark:text-[#818CF8]",
    borderDark: "dark:border-[#6366F1]/40",
  },
  IN_COMMUNICATION: {
    label: "In Communication",
    bgLight: "bg-[#ECFDF5]",
    textLight: "text-[#047857]",
    borderLight: "border-[#A7F3D0]",
    bgDark: "dark:bg-[#062D1F]",
    textDark: "dark:text-[#34D399]",
    borderDark: "dark:border-[#10B981]/40",
  },
  QUOTATION_PENDING: {
    label: "Quotation Pending",
    bgLight: "bg-[#F3E8FF]",
    textLight: "text-[#7E22CE]",
    borderLight: "border-[#E9D5FF]",
    bgDark: "dark:bg-[#2E1065]/40",
    textDark: "dark:text-[#C084FC]",
    borderDark: "dark:border-[#A855F7]/40",
  },
  COMPLETED: {
    label: "Completed",
    bgLight: "bg-[#CCFBF1]",
    textLight: "text-[#0F766E]",
    borderLight: "border-[#99F6E4]",
    bgDark: "dark:bg-[#134E4A]/40",
    textDark: "dark:text-[#2DD4BF]",
    borderDark: "dark:border-[#14B8A6]/40",
  },
  DECLINED: {
    label: "Declined",
    bgLight: "bg-[#FEF2F2]",
    textLight: "text-[#B91C1C]",
    borderLight: "border-[#FECACA]",
    bgDark: "dark:bg-[#2C1111]",
    textDark: "dark:text-[#F87171]",
    borderDark: "dark:border-[#EF4444]/40",
  },
  ARCHIVED: {
    label: "Archived",
    bgLight: "bg-panel-2",
    textLight: "text-ink-muted",
    borderLight: "border-line-strong",
    bgDark: "dark:bg-[#1E293B]",
    textDark: "dark:text-[#94A3B8]",
    borderDark: "dark:border-[#475569]/40",
  },
};

export function EnquiryDossierHeader({
  dossier,
  onRefresh,
  isLoading,
  onOpenAssignModal,
  onOpenStatusModal,
}: EnquiryDossierHeaderProps) {
  const [copied, setCopied] = useState(false);

  const statusConfig = STATUS_CONFIG[dossier.status] || {
    label: dossier.status,
    bgLight: "bg-panel-2",
    textLight: "text-ink-muted",
    borderLight: "border-line-strong",
    bgDark: "dark:bg-[#1E293B]",
    textDark: "dark:text-[#94A3B8]",
    borderDark: "dark:border-[#475569]",
  };

  const handleCopyRef = async () => {
    try {
      await navigator.clipboard.writeText(dossier.reference_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard error
    }
  };

  const formattedCreated = new Date(dossier.created_at).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
  const formattedUpdated = new Date(dossier.updated_at).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");

  return (
    <div className="space-y-4">
      {/* Top Navigation & Breadcrumbs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs font-heading">
          <Link
            href="/admin/enquiries"
            className="inline-flex items-center gap-1.5 text-ink-subtle hover:text-ink transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Enquiries Repository</span>
          </Link>
          <span className="text-line-strong">/</span>
          <span className="font-mono font-medium text-ink">
            {dossier.reference_number}
          </span>
        </div>

        {/* Workflow Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {onOpenAssignModal && (
            <button
              type="button"
              onClick={onOpenAssignModal}
              aria-label="Assign or transfer enquiry"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] text-xs font-mono font-medium border border-brand/40 bg-brand-soft text-brand hover:bg-brand-soft dark:hover:bg-[#003B46] transition-colors cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand"
              title="Assign or reassign handling administrator"
            >
              <UserCheck className="h-3.5 w-3.5" />
              <span>Assign / Transfer</span>
            </button>
          )}

          {onOpenStatusModal && (
            <button
              type="button"
              onClick={onOpenStatusModal}
              aria-label="Update enquiry operational status"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] text-xs font-mono font-medium border border-line bg-panel text-ink hover:border-line-strong hover:bg-panel-2 transition-colors cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand"
              title="Advance or transition commercial lifecycle status"
            >
              <RefreshCw className="h-3.5 w-3.5 text-brand" />
              <span>Update Status</span>
            </button>
          )}

          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] text-xs font-mono font-medium border border-line bg-panel text-ink-subtle hover:text-ink hover:border-line-strong transition-colors disabled:opacity-50 cursor-pointer"
            title="Refresh enquiry snapshot and timeline"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin text-brand " : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Primary Dossier Header Card */}
      <div className="p-5 sm:p-6 rounded-[2px] border border-line eb-glass shadow-2xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Reference & Title */}
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-lg sm:text-xl font-bold tracking-tight text-ink">
                {dossier.reference_number}
              </span>

              <button
                type="button"
                onClick={handleCopyRef}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] text-[11px] font-mono text-ink-subtle hover:bg-panel-2 transition-colors cursor-pointer"
                title="Copy Reference Number"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-[#059669] dark:text-[#10B981]" />
                    <span className="text-[#059669] dark:text-[#10B981]">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>

              {/* Lifecycle Status Pill */}
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-[2px] text-xs font-mono font-medium border ${statusConfig.bgLight} ${statusConfig.textLight} ${statusConfig.borderLight} ${statusConfig.bgDark} ${statusConfig.textDark} ${statusConfig.borderDark}`}
              >
                {statusConfig.label}
              </span>
            </div>

            <p className="text-sm font-heading font-medium text-ink-muted">
              {dossier.company_name} — {dossier.product_focus}
            </p>
          </div>

          {/* Operational Badges & Metadata */}
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            {/* Division Pill */}
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-panel-2 border border-line text-ink">
              <span
                className="h-2 w-2 rounded-full shrink-0"
                style={{ backgroundColor: dossier.current_division.accent_color || "#0284C7" }}
              />
              <span className="font-medium">{dossier.current_division.name}</span>
            </div>

            {/* Assigned Admin Chip */}
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] bg-panel-2 border border-line text-ink-muted">
              <User className="h-3.5 w-3.5 text-ink-subtle" />
              {dossier.assigned_admin ? (
                <span className="font-medium text-ink">
                  {dossier.assigned_admin.name}
                </span>
              ) : (
                <span className="text-ink-subtle italic">Unassigned</span>
              )}
            </div>

            {/* Ingestion Date */}
            <div className="inline-flex items-center gap-1.5 text-ink-subtle text-[11px]">
              <Clock className="h-3.5 w-3.5 text-ink-subtle" />
              <span>Intake: {formattedCreated}</span>
            </div>
          </div>
        </div>

        {/* Read-Only Operational Notice */}
        <div className="mt-4 pt-3.5 border-t border-line flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-ink-subtle">
          <div className="flex items-center gap-1.5">
            <ShieldAlert className="h-3.5 w-3.5 text-brand" />
            <span>Commercial Confidentiality: Central authorized administrative access only.</span>
          </div>
          <div>Last Updated: {formattedUpdated}</div>
        </div>
      </div>
    </div>
  );
}
