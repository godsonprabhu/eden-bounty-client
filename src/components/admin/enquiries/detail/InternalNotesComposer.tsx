"use client";

import React, { useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  Lock,
  MessageSquarePlus,
  RefreshCw,
  Send,
} from "lucide-react";
import { EnquiryNoteItem } from "@/types/admin";
import { AdminApiError, apiAddEnquiryNote } from "@/lib/admin-api";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { useToast } from "@/hooks/useToast";
import { sanitizeErrorMessage } from "@/components/ui/states/StateError";

interface InternalNotesComposerProps {
  enquiryId: string;
  onNoteAdded: (note: EnquiryNoteItem) => void;
}

export function InternalNotesComposer({
  enquiryId,
  onNoteAdded,
}: InternalNotesComposerProps) {
  const { user, csrfToken } = useAdminAuth();
  const { toast } = useToast();

  const [noteText, setNoteText] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const trimmedText = noteText.trim();
  const isValid = trimmedText.length >= 1 && trimmedText.length <= 4000;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || !isValid) return;

    if (trimmedText.length < 1) {
      setErrorMessage("Note content cannot be empty.");
      return;
    }

    if (trimmedText.length > 4000) {
      setErrorMessage("Note content cannot exceed 4,000 characters.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setShowSuccess(false);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const createdNote = await apiAddEnquiryNote(
        enquiryId,
        { note_text: trimmedText },
        csrfToken,
        { signal: controller.signal }
      );

      setIsSubmitting(false);
      setNoteText("");
      setShowSuccess(true);
      toast.success("Internal note recorded successfully.");
      onNoteAdded(createdNote);

      setTimeout(() => setShowSuccess(false), 3000);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setIsSubmitting(false);

      if (err instanceof AdminApiError) {
        if (err.status === 403) {
          setErrorMessage(
            "Authorization failed: Insufficient permissions or CSRF token expired. Please refresh the page."
          );
        } else if (err.status === 422) {
          setErrorMessage(`Validation error (422): ${sanitizeErrorMessage(err.detail)}`);
        } else if (err.status === 404) {
          setErrorMessage("Enquiry record was not found or has been removed.");
        } else {
          setErrorMessage(sanitizeErrorMessage(err.detail || "Failed to record internal note. Please try again."));
        }
      } else if (err instanceof Error) {
        setErrorMessage(sanitizeErrorMessage(err.message));
      } else {
        setErrorMessage("An unexpected error occurred while appending the note.");
      }
    }
  };

  const authorName = user ? `${user.first_name} ${user.last_name}`.trim() : "System Administrator";
  const authorEmail = user?.email || "";

  return (
    <div className="p-4 sm:p-5 rounded-[2px] bg-panel-2 border border-line space-y-3.5">
      {/* Author and Permanent Notice Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
        <div className="flex items-center gap-1.5">
          <MessageSquarePlus className="h-3.5 w-3.5 text-brand" />
          <span className="font-heading font-semibold text-ink">
            Add Internal Note
          </span>
          <span className="text-ink-subtle">
            — Posting as <span className="text-ink">{authorName}</span>{authorEmail ? ` (${authorEmail})` : ""}
          </span>
        </div>

        <div className="inline-flex items-center gap-1 text-[11px] text-ink-muted">
          <Lock className="h-3 w-3" />
          <span>Append-Only</span>
        </div>
      </div>

      {/* Immutability & Confidentiality Cue */}
      <p className="text-[11px] font-mono text-ink-subtle leading-relaxed">
        Internal notes are strictly restricted to central operations staff and are never visible to external clients. Once submitted, records are immutable and cannot be edited or deleted.
      </p>

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-3 rounded-[2px] bg-[#FEF2F2] dark:bg-[#2C1111] border border-[#FECACA] dark:border-[#EF4444]/40 text-xs font-mono text-[#B91C1C] dark:text-[#F87171] flex items-start gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <div className="flex-1">{errorMessage}</div>
        </div>
      )}

      {/* Success Banner */}
      {showSuccess && (
        <div className="p-2.5 rounded-[2px] bg-[#ECFDF5] dark:bg-[#062D1F] border border-[#A7F3D0] dark:border-[#10B981]/40 text-xs font-mono text-[#047857] dark:text-[#34D399] flex items-center gap-2">
          <Check className="h-3.5 w-3.5 shrink-0" />
          <span>Internal note appended successfully to commercial audit record.</span>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-2.5">
        <div className="space-y-1">
          <textarea
            id="internal-note-textarea"
            aria-label="Internal operational note content"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            disabled={isSubmitting}
            maxLength={4000}
            rows={3}
            placeholder="Record client communication details, trade specifications clarifications, bank guarantee updates, or commercial triage notes..."
            className="w-full p-3 rounded-[2px] border border-line bg-panel text-xs font-mono text-ink placeholder:text-ink-subtle focus:outline-hidden focus:border-brand transition-colors resize-y disabled:opacity-50"
          />

          <div className="flex items-center justify-between text-[11px] font-mono text-ink-subtle">
            <span>Markdown formatting supported in plain text.</span>
            <span
              className={
                trimmedText.length > 4000
                  ? "text-[#B91C1C] dark:text-[#F87171] font-bold"
                  : ""
              }
            >
              {trimmedText.length} / 4000
            </span>
          </div>
        </div>

        <div className="flex items-center justify-end">
          <button
            type="submit"
            disabled={isSubmitting || !isValid}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-[2px] bg-brand text-xs font-mono font-semibold text-brand-ink dark:text-[#000000] hover:bg-brand-hover dark:hover:bg-[#00D0DF] transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="h-3 w-3 animate-spin" />
                <span>Recording...</span>
              </>
            ) : (
              <>
                <Send className="h-3 w-3" />
                <span>Add Note</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
