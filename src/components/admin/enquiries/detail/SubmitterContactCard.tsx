"use client";

import React, { useState } from "react";
import {
  Building2,
  Check,
  Copy,
  Globe2,
  Mail,
  Phone,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { EnquiryDetailResponseData } from "@/types/admin";

interface SubmitterContactCardProps {
  dossier: EnquiryDetailResponseData;
}

export function SubmitterContactCard({ dossier }: SubmitterContactCardProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const contactNumber = dossier.contact_number;

  const copyToClipboard = async (field: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      // Ignore clipboard error
    }
  };

  return (
    <div className="rounded-[2px] border border-line eb-glass p-5 shadow-2xs space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-line">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
            <Building2 className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-xs font-heading font-bold uppercase tracking-wider text-ink">
              Commercial Contact Snapshot
            </h2>
            <p className="text-[11px] font-mono text-ink-subtle">
              Authorized corporate entity details
            </p>
          </div>
        </div>

        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-[#059669] dark:text-[#10B981] bg-[#ECFDF5] dark:bg-[#062D1F] px-2 py-0.5 rounded-[2px] border border-[#A7F3D0] dark:border-[#10B981]/40">
          <ShieldCheck className="h-3 w-3" />
          <span>Verified</span>
        </span>
      </div>

      {/* Corporate Entity & Submitter Details */}
      <div className="space-y-3.5 text-xs font-mono">
        {/* Company Name */}
        <div>
          <span className="text-[11px] uppercase tracking-wider text-ink-subtle block mb-0.5">
            Registered Entity / Company
          </span>
          <div className="flex items-center justify-between p-2 rounded-[2px] bg-panel-2 border border-line">
            <span className="font-heading font-semibold text-ink text-sm truncate">
              {dossier.company_name}
            </span>
            <button
              type="button"
              onClick={() => copyToClipboard("company", dossier.company_name)}
              className="p-1 text-ink-subtle hover:text-ink cursor-pointer"
              title="Copy company name"
            >
              {copiedField === "company" ? (
                <Check className="h-3.5 w-3.5 text-[#059669] dark:text-[#10B981]" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Contact Representative */}
        <div>
          <span className="text-[11px] uppercase tracking-wider text-ink-subtle block mb-0.5">
            Submitter Full Name
          </span>
          <div className="flex items-center gap-2 p-2 rounded-[2px] bg-panel-2 border border-line">
            <UserCheck className="h-4 w-4 text-ink-subtle shrink-0" />
            <span className="font-medium text-ink truncate">
              {dossier.full_name}
            </span>
          </div>
        </div>

        {/* Business Email */}
        <div>
          <span className="text-[11px] uppercase tracking-wider text-ink-subtle block mb-0.5">
            Business Email
          </span>
          <div className="flex items-center justify-between p-2 rounded-[2px] bg-panel-2 border border-line">
            <a
              href={`mailto:${dossier.business_email}`}
              className="flex items-center gap-2 text-brand hover:underline truncate"
              title={`Compose email to ${dossier.business_email}`}
            >
              <Mail className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{dossier.business_email}</span>
            </a>
            <button
              type="button"
              onClick={() => copyToClipboard("email", dossier.business_email)}
              className="p-1 text-ink-subtle hover:text-ink cursor-pointer shrink-0 ml-1"
              title="Copy email address"
            >
              {copiedField === "email" ? (
                <Check className="h-3.5 w-3.5 text-[#059669] dark:text-[#10B981]" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Contact Phone */}
        <div>
          <span className="text-[11px] uppercase tracking-wider text-ink-subtle block mb-0.5">
            Contact Number
          </span>
          <div className="flex items-center justify-between p-2 rounded-[2px] bg-panel-2 border border-line">
            {contactNumber ? (
              <>
                <a
                  href={`tel:${contactNumber}`}
                  className="flex items-center gap-2 text-ink hover:text-brand truncate"
                  title={`Call ${contactNumber}`}
                >
                  <Phone className="h-3.5 w-3.5 text-ink-subtle shrink-0" />
                  <span className="truncate">{contactNumber}</span>
                </a>
                <button
                  type="button"
                  onClick={() => copyToClipboard("phone", contactNumber)}
                  className="p-1 text-ink-subtle hover:text-ink cursor-pointer shrink-0 ml-1"
                  title="Copy phone number"
                >
                  {copiedField === "phone" ? (
                    <Check className="h-3.5 w-3.5 text-[#059669] dark:text-[#10B981]" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </>
            ) : (
              <span className="text-ink-subtle">Not provided</span>
            )}
          </div>
        </div>

        {/* Jurisdiction / Country */}
        <div>
          <span className="text-[11px] uppercase tracking-wider text-ink-subtle block mb-0.5">
            Operating Country / Jurisdiction
          </span>
          <div className="flex items-center gap-2 p-2 rounded-[2px] bg-panel-2 border border-line">
            <Globe2 className="h-3.5 w-3.5 text-brand shrink-0" />
            <span className="text-ink font-medium">
              {dossier.country}
            </span>
          </div>
        </div>
      </div>

      {/* Footer Confidentiality Notice */}
      <div className="pt-2 text-[11px] font-mono text-ink-subtle border-t border-line">
        Data Protection Notice: Contact details isolated to central operations dossier view.
      </div>
    </div>
  );
}
