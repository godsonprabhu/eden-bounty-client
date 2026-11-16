"use client";

import React from "react";
import { Clock, Lock, MessageSquare, ShieldAlert, User } from "lucide-react";
import { EnquiryNoteItem } from "@/types/admin";
import { InternalNotesComposer } from "./InternalNotesComposer";

interface InternalNotesSectionProps {
  notes: EnquiryNoteItem[];
  enquiryId: string;
  onNoteAdded: (note: EnquiryNoteItem) => void;
}

export function InternalNotesSection({
  notes,
  enquiryId,
  onNoteAdded,
}: InternalNotesSectionProps) {
  return (
    <div className="rounded-[2px] border border-line eb-glass p-5 sm:p-6 shadow-2xs space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
            <MessageSquare className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-xs font-heading font-bold uppercase tracking-wider text-ink">
              Internal Operational Notes
            </h2>
            <p className="text-[11px] font-mono text-ink-subtle">
              Central trade comments and operational follow-ups ({notes.length})
            </p>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-[2px] bg-[#FEF2F2] dark:bg-[#2C1111] border border-[#FECACA] dark:border-[#EF4444]/40 text-[11px] font-mono text-[#B91C1C] dark:text-[#F87171]">
          <Lock className="h-3 w-3" />
          <span>Internal Only</span>
        </div>
      </div>

      {/* Security Banner */}
      <div className="p-3 rounded-[2px] bg-[#FFFBEB] dark:bg-[#2D2312] border border-[#FDE68A] dark:border-[#F59E0B]/40 text-xs font-mono text-[#B45309] dark:text-[#FBBF24] flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 shrink-0" />
        <span>
          Confidential Operational Record: Notes are strictly restricted to authenticated central administrators and are never exposed via external APIs.
        </span>
      </div>

      {/* Interactive Notes Composer */}
      <InternalNotesComposer enquiryId={enquiryId} onNoteAdded={onNoteAdded} />

      {/* Notes List */}
      {notes.length === 0 ? (
        <div className="text-center py-6 border border-dashed border-line rounded-[2px] text-xs font-mono text-ink-subtle">
          No internal operational notes recorded for this enquiry.
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((note) => {
            const formattedDate = new Date(note.created_at)
              .toISOString()
              .replace("T", " ")
              .replace(/\.\d{3}Z$/, " UTC");

            return (
              <div
                key={note.id}
                className="p-4 rounded-[2px] bg-panel-2 border border-line space-y-2 text-xs font-mono"
              >
                {/* Note Author & Timestamp Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-line">
                  <div className="flex items-center gap-2">
                    <User className="h-3.5 w-3.5 text-brand" />
                    <span className="font-heading font-semibold text-ink">
                      {note.author_admin?.name || "Administrator"}
                    </span>
                    {note.author_admin?.email && (
                      <span className="text-[11px] text-ink-subtle">
                        ({note.author_admin.email})
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] text-ink-subtle">
                    <Clock className="h-3 w-3 text-ink-subtle" />
                    <span>{formattedDate}</span>
                  </div>
                </div>

                {/* Note Content */}
                <div className="text-ink-muted whitespace-pre-wrap leading-relaxed">
                  {note.note_text}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
