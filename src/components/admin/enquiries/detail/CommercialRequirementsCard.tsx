"use client";

import React from "react";
import {
  Anchor,
  Box,
  FileText,
  Layers,
  Scale,
  ShieldAlert,
  Tag,
} from "lucide-react";
import { EnquiryDetailResponseData } from "@/types/admin";

interface CommercialRequirementsCardProps {
  dossier: EnquiryDetailResponseData;
}

export function CommercialRequirementsCard({ dossier }: CommercialRequirementsCardProps) {
  const isDivisionReassigned =
    dossier.initial_division &&
    dossier.current_division &&
    dossier.initial_division.id !== dossier.current_division.id;

  const formattedQuantity = dossier.quantity
    ? Number(dossier.quantity).toLocaleString("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      })
    : null;

  return (
    <div className="rounded-[2px] border border-line eb-glass p-5 sm:p-6 shadow-2xs space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between pb-3.5 border-b border-line">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
            <Box className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-xs font-heading font-bold uppercase tracking-wider text-ink">
              Commercial Specifications & Scope
            </h2>
            <p className="text-[11px] font-mono text-ink-subtle">
              Original trade requirements submitted by client
            </p>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-[2px] bg-panel-2 border border-line text-xs font-mono">
          <Tag className="h-3 w-3 text-ink-subtle" />
          <span className="font-medium text-ink">
            {dossier.current_division.name}
          </span>
        </div>
      </div>

      {/* Grid of Key Commercial Parameters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
        {/* Product Focus */}
        <div className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-ink-subtle">
            <Tag className="h-3 w-3 text-brand" />
            <span>Target Commodity / Product Focus</span>
          </div>
          <div className="font-heading font-semibold text-sm text-ink">
            {dossier.product_focus}
          </div>
        </div>

        {/* Quantity & Measurement */}
        <div className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-ink-subtle">
            <Scale className="h-3 w-3 text-brand" />
            <span>Target Volume / Measurement</span>
          </div>
          <div className="font-heading font-semibold text-sm text-ink">
            {formattedQuantity ? (
              <>
                <span>{formattedQuantity}</span>
                {dossier.unit_of_measurement && (
                  <span className="ml-1.5 text-xs font-mono font-normal text-ink-subtle">
                    {dossier.unit_of_measurement}
                  </span>
                )}
              </>
            ) : (
              <span className="text-ink-subtle italic">Not Specified</span>
            )}
          </div>
        </div>

        {/* Incoterm */}
        <div className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-ink-subtle">
            <Anchor className="h-3 w-3 text-brand" />
            <span>Preferred Incoterm</span>
          </div>
          <div className="font-heading font-semibold text-sm text-ink">
            {dossier.preferred_incoterm ? (
              <span className="px-2 py-0.5 rounded-[2px] bg-brand-soft text-brand border border-brand/40">
                {dossier.preferred_incoterm}
              </span>
            ) : (
              <span className="text-ink-subtle italic">Standard Terms</span>
            )}
          </div>
        </div>

        {/* Destination Port */}
        <div className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-ink-subtle">
            <Anchor className="h-3 w-3 text-brand" />
            <span>Target Destination Port / Terminal</span>
          </div>
          <div className="font-heading font-medium text-xs text-ink">
            {dossier.target_destination_port || (
              <span className="text-ink-subtle italic">To Be Agreed</span>
            )}
          </div>
        </div>
      </div>

      {/* Division Reassignment Notice if applicable */}
      {isDivisionReassigned && (
        <div className="p-3 rounded-[2px] bg-[#FFFBEB] dark:bg-[#2D2312] border border-[#FDE68A] dark:border-[#F59E0B]/40 text-xs font-mono text-[#B45309] dark:text-[#FBBF24] flex items-center gap-2">
          <Layers className="h-4 w-4 shrink-0" />
          <span>
            Division Reassignment Recorded: Originally submitted to{" "}
            <strong>{dossier.initial_division.name}</strong>, currently managed under{" "}
            <strong>{dossier.current_division.name}</strong>.
          </span>
        </div>
      )}

      {/* Technical Specifications Block */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-heading font-semibold uppercase tracking-wider text-ink-muted">
          <FileText className="h-3.5 w-3.5 text-brand" />
          <span>Detailed Commercial & Technical Specifications</span>
        </div>
        <div className="p-4 rounded-[2px] bg-panel-2 border border-line text-xs font-mono text-ink whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
          {dossier.specifications || (
            <span className="text-ink-subtle italic">
              No technical specifications submitted.
            </span>
          )}
        </div>
      </div>

      {/* Additional Submitter Notes Block */}
      {dossier.additional_notes && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-heading font-semibold uppercase tracking-wider text-ink-muted">
            <ShieldAlert className="h-3.5 w-3.5 text-[#F59E0B]" />
            <span>Additional Submitter Remarks</span>
          </div>
          <div className="p-4 rounded-[2px] bg-panel-2 border border-line text-xs font-mono text-ink whitespace-pre-wrap leading-relaxed">
            {dossier.additional_notes}
          </div>
        </div>
      )}
    </div>
  );
}
