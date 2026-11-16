"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ExternalLink,
  Globe,
  Building2,
  User,
  AlertCircle,
} from "lucide-react";
import { EnquiryListItem } from "@/types/admin";

interface EnquiryTableProps {
  items: EnquiryListItem[];
  sortBy: string;
  sortOrder: "asc" | "desc";
  onSortChange: (column: "created_at" | "reference_number" | "company_name" | "status") => void;
}

function getStatusBadge(status: string) {
  switch (status) {
    case "NEW":
      return {
        label: "New Intake",
        className:
          "border-brand/40 dark:border-[#0369A1] bg-brand-soft dark:bg-[#082F49] text-brand dark:text-[#38BDF8]",
      };
    case "UNDER_REVIEW":
      return {
        label: "Under Review",
        className:
          "border-[#FDE68A] dark:border-[#B45309] bg-[#FEF3C7] dark:bg-[#451A03] text-[#D97706] dark:text-[#F59E0B]",
      };
    case "ASSIGNED":
      return {
        label: "Assigned",
        className:
          "border-[#C7D2FE] dark:border-[#4338CA] bg-[#EEF2FF] dark:bg-[#1E1B4B] text-[#4F46E5] dark:text-[#818CF8]",
      };
    case "IN_COMMUNICATION":
      return {
        label: "In Communication",
        className:
          "border-[#A7F3D0] dark:border-[#047857] bg-[#D1FAE5] dark:bg-[#064E3B] text-[#059669] dark:text-[#10B981]",
      };
    case "QUOTATION_PENDING":
      return {
        label: "Quotation Pending",
        className:
          "border-[#DDD6FE] dark:border-[#6D28D9] bg-[#F3E8FF] dark:bg-[#3B0764] text-[#7C3AED] dark:text-[#A855F7]",
      };
    case "COMPLETED":
      return {
        label: "Completed",
        className:
          "border-[#99F6E4] dark:border-[#0F766E] bg-[#CCFBF1] dark:bg-[#134E4A] text-[#0D9488] dark:text-[#2DD4BF]",
      };
    case "DECLINED":
      return {
        label: "Declined",
        className:
          "border-[#FECDD3] dark:border-[#BE123C] bg-[#FFE4E6] dark:bg-[#4C0519] text-[#E11D48] dark:text-[#FB7185]",
      };
    case "ARCHIVED":
      return {
        label: "Archived",
        className:
          "border-line-strong  bg-panel-2  text-ink-muted ",
      };
    default:
      return {
        label: status,
        className:
          "border-line  bg-panel-2  text-ink-subtle ",
      };
  }
}

export function EnquiryTable({
  items,
  sortBy,
  sortOrder,
  onSortChange,
}: EnquiryTableProps) {
  const renderSortIndicator = (column: string) => {
    if (sortBy !== column) {
      return <ArrowUpDown className="h-3 w-3 text-ink-subtle opacity-60 ml-1 inline-block" />;
    }
    return sortOrder === "asc" ? (
      <ArrowUp className="h-3 w-3 text-brand ml-1 inline-block" />
    ) : (
      <ArrowDown className="h-3 w-3 text-brand ml-1 inline-block" />
    );
  };

  return (
    <div className="rounded-[2px] border border-line eb-glass shadow-2xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[860px]">
          <thead>
            <tr className="border-b border-line bg-panel-2">
              {/* Reference Number */}
              <th scope="col" className="py-3 px-4">
                <button
                  type="button"
                  onClick={() => onSortChange("reference_number")}
                  className="flex items-center text-[10px] font-mono uppercase tracking-wider text-ink-subtle hover:text-ink cursor-pointer"
                >
                  <span>Reference #</span>
                  {renderSortIndicator("reference_number")}
                </button>
              </th>

              {/* Submission Date (UTC) */}
              <th scope="col" className="py-3 px-4">
                <button
                  type="button"
                  onClick={() => onSortChange("created_at")}
                  className="flex items-center text-[10px] font-mono uppercase tracking-wider text-ink-subtle hover:text-ink cursor-pointer"
                >
                  <span>Submission Date (UTC)</span>
                  {renderSortIndicator("created_at")}
                </button>
              </th>

              {/* Commercial Division */}
              <th
                scope="col"
                className="py-3 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle"
              >
                Commercial Division
              </th>

              {/* Company & Country (Privacy-Safe: Strictly NO submitter name/email) */}
              <th scope="col" className="py-3 px-4">
                <button
                  type="button"
                  onClick={() => onSortChange("company_name")}
                  className="flex items-center text-[10px] font-mono uppercase tracking-wider text-ink-subtle hover:text-ink cursor-pointer"
                >
                  <span>Company / Country</span>
                  {renderSortIndicator("company_name")}
                </button>
              </th>

              {/* Lifecycle Status */}
              <th scope="col" className="py-3 px-4">
                <button
                  type="button"
                  onClick={() => onSortChange("status")}
                  className="flex items-center text-[10px] font-mono uppercase tracking-wider text-ink-subtle hover:text-ink cursor-pointer"
                >
                  <span>Status</span>
                  {renderSortIndicator("status")}
                </button>
              </th>

              {/* Assigned Administrator */}
              <th
                scope="col"
                className="py-3 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle"
              >
                Assigned Administrator
              </th>

              {/* Actions */}
              <th
                scope="col"
                className="py-3 px-4 text-right text-[10px] font-mono uppercase tracking-wider text-ink-subtle"
              >
                Actions
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-panel-2">
            {items.map((enq) => {
              const badge = getStatusBadge(enq.status);
              const createdDate = new Date(enq.created_at);
              const formattedDate = createdDate.toLocaleDateString("en-GB", {
                timeZone: "UTC",
                year: "numeric",
                month: "short",
                day: "2-digit",
              });
              const formattedTime = createdDate.toLocaleTimeString("en-GB", {
                timeZone: "UTC",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <tr
                  key={enq.id}
                  className="hover:bg-panel-2 transition-colors"
                >
                  {/* Reference Number */}
                  <td className="py-3 px-4">
                    <span className="font-mono text-xs font-semibold text-ink">
                      {enq.reference_number}
                    </span>
                  </td>

                  {/* Submission Date (UTC) */}
                  <td className="py-3 px-4">
                    <span className="text-xs font-mono text-ink-subtle">
                      {formattedDate} {formattedTime} UTC
                    </span>
                  </td>

                  {/* Commercial Division */}
                  <td className="py-3 px-4">
                    <span className="text-xs font-heading font-medium text-ink">
                      {enq.division_name}
                    </span>
                  </td>

                  {/* Company & Country (Privacy Guard: NO submitter personal name or email) */}
                  <td className="py-3 px-4">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-1.5">
                        <Building2 className="h-3 w-3 text-ink-subtle shrink-0" />
                        <span className="text-xs font-heading font-medium text-ink truncate max-w-[180px]">
                          {enq.company_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 text-[11px] font-body text-ink-subtle mt-0.5">
                        <Globe className="h-2.5 w-2.5 text-ink-subtle shrink-0" />
                        <span>{enq.country}</span>
                      </div>
                    </div>
                  </td>

                  {/* Lifecycle Status Badge */}
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-[2px] text-[10px] font-heading font-semibold border ${badge.className}`}
                    >
                      {badge.label}
                    </span>
                  </td>

                  {/* Assigned Administrator Pill */}
                  <td className="py-3 px-4">
                    {enq.assigned_admin ? (
                      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[2px] text-xs font-body bg-panel-2 text-ink-muted border border-line-strong">
                        <User className="h-3 w-3 text-brand" />
                        <span className="truncate max-w-[120px]">{enq.assigned_admin.name}</span>
                      </div>
                    ) : (
                      <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] text-[11px] font-body text-[#D97706] dark:text-[#F59E0B] bg-[#FEF3C7] dark:bg-[#451A03] border border-[#FDE68A] dark:border-[#B45309]">
                        <AlertCircle className="h-2.5 w-2.5" />
                        <span>Unassigned</span>
                      </div>
                    )}
                  </td>

                  {/* Action Link: View Dossier */}
                  <td className="py-3 px-4 text-right">
                    <Link
                      href={`/admin/enquiries/${enq.id}`}
                      aria-label={`View dossier for ${enq.reference_number}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[2px] text-xs font-heading font-semibold text-brand bg-brand-soft/60 hover:bg-brand-soft border border-brand/40 transition-colors cursor-pointer"
                    >
                      <span>View Dossier</span>
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
