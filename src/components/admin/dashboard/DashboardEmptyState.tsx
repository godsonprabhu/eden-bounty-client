"use client";

import React from "react";
import { Inbox, ExternalLink } from "lucide-react";
import Link from "next/link";

export function DashboardEmptyState() {
  return (
    <div className="p-8 sm:p-12 rounded-[2px] border border-line-strong eb-glass text-center max-w-2xl mx-auto my-12 shadow-xs">
      <div className="h-12 w-12 rounded-[2px] bg-brand-soft flex items-center justify-center mx-auto mb-4 border border-brand/40">
        <Inbox className="h-6 w-6 text-brand" />
      </div>

      <h2 className="text-lg font-heading font-bold text-ink">
        Commercial Pipeline Repository Empty
      </h2>

      <p className="mt-2 text-xs font-body text-ink-subtle max-w-md mx-auto leading-relaxed">
        There are currently zero commercial enquiry submissions recorded in the database.
        As clients submit Trade Enquiry (RFQ) forms on the public corporate portal, they will appear here in real time.
      </p>

      <div className="mt-6 flex items-center justify-center gap-3">
        <Link
          href="/#trade-inquiry"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-[2px] bg-brand text-brand-ink text-xs font-heading font-semibold hover:opacity-90 transition-opacity"
        >
          <span>Open Public RFQ Form</span>
          <ExternalLink className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
