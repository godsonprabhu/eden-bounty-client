"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";

interface EnquiryDossierNotFoundProps {
  id?: string;
}

export function EnquiryDossierNotFound({ id }: EnquiryDossierNotFoundProps) {
  return (
    <div className="max-w-2xl mx-auto py-12 text-center space-y-6">
      <div className="p-8 sm:p-12 rounded-[2px] border border-line eb-glass shadow-2xs space-y-4">
        <div className="h-14 w-14 rounded-[2px] bg-[#EFF6FF] dark:bg-[#112240] flex items-center justify-center mx-auto border border-[#BFDBFE] dark:border-[#1E3A8A]">
          <FileQuestion className="h-7 w-7 text-[#1D4ED8] dark:text-[#60A5FA]" />
        </div>

        <h1 className="text-lg sm:text-xl font-heading font-bold text-ink">
          Commercial Enquiry Not Found
        </h1>

        {id && (
          <p className="font-mono text-xs text-ink-subtle">
            Enquiry Identifier: <span className="text-brand">{id}</span>
          </p>
        )}

        <p className="text-xs font-body text-ink-subtle max-w-md mx-auto leading-relaxed">
          The requested trade enquiry record does not exist or has been archived from the central repository. Please verify the reference identifier or return to the enquiries console.
        </p>

        <div className="pt-4 flex items-center justify-center gap-3">
          <Link
            href="/admin/enquiries"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[2px] text-xs font-heading font-medium text-brand-ink bg-brand dark:text-[#000000] hover:bg-brand-hover transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Return to Repository</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
