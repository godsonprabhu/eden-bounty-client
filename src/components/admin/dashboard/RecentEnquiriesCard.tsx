"use client";

import React from "react";
import { EnquiryListItem } from "@/types/admin";
import { Inbox, ShieldAlert, User, Clock } from "lucide-react";

interface RecentEnquiriesCardProps {
  enquiries: EnquiryListItem[];
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

export function RecentEnquiriesCard({ enquiries }: RecentEnquiriesCardProps) {
  return (
    <div className="p-5 sm:p-6 rounded-[2px] border border-line eb-glass shadow-2xs">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-line">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-[2px] bg-brand-soft flex items-center justify-center shrink-0 border border-brand/40">
            <Inbox className="h-4 w-4 text-brand" />
          </div>
          <div>
            <h2 className="text-sm font-heading font-bold text-ink">
              Recent Commercial Enquiries
            </h2>
            <p className="text-[11px] font-body text-ink-subtle">
              Latest 5 incoming submissions (Strictly Read-Only Overview)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-[10px] font-mono text-ink-subtle">
          <Clock className="h-3 w-3" />
          <span>Descending by created_at (UTC)</span>
        </div>
      </div>

      {/* Compact Read-Only Table */}
      {enquiries.length === 0 ? (
        <div className="py-8 text-center border border-dashed border-line-strong rounded-[2px] bg-panel-2">
          <p className="text-xs font-body text-ink-subtle">
            No commercial enquiries registered in the database repository.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto -mx-5 sm:mx-0">
          <table className="w-full text-left border-collapse min-w-[620px]">
            <thead>
              <tr className="border-b border-line bg-panel-2">
                <th className="py-2.5 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
                  Reference #
                </th>
                <th className="py-2.5 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
                  Commercial Division
                </th>
                <th className="py-2.5 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
                  Submission Date (UTC)
                </th>
                <th className="py-2.5 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
                  Lifecycle Status
                </th>
                <th className="py-2.5 px-4 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
                  Assigned Administrator
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-panel-2">
              {enquiries.map((enq) => {
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

                    {/* Division */}
                    <td className="py-3 px-4">
                      <span className="text-xs font-heading font-medium text-ink">
                        {enq.division_name}
                      </span>
                    </td>

                    {/* Submission Date */}
                    <td className="py-3 px-4">
                      <span className="text-xs font-mono text-ink-subtle">
                        {formattedDate} {formattedTime} UTC
                      </span>
                    </td>

                    {/* Status Badge */}
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-[2px] text-[10px] font-heading font-semibold border ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </td>

                    {/* Assigned Administrator */}
                    <td className="py-3 px-4">
                      {enq.assigned_admin ? (
                        <div className="flex items-center gap-1.5">
                          <User className="h-3 w-3 text-brand" />
                          <span className="text-xs font-body font-medium text-ink">
                            {enq.assigned_admin.name}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded-[2px] bg-[#FEF3C7] dark:bg-[#451A03] text-[#D97706] dark:text-[#F59E0B] text-[10px] font-mono border border-[#FDE68A] dark:border-[#B45309]">
                          Unassigned
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Confidentiality Notice */}
      <div className="mt-4 pt-3 border-t border-line flex items-center gap-2 text-[10px] font-mono text-ink-subtle">
        <ShieldAlert className="h-3.5 w-3.5 text-brand shrink-0" />
        <span>
          Data Confidentiality Policy: Submitter personal contact credentials (email, telephone) are
          strictly omitted from overview and restricted to authorized dossiers.
        </span>
      </div>
    </div>
  );
}
