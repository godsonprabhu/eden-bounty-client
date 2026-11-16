"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react";
import {
  EnquiryDetailResponseData,
  PERMITTED_STATUS_TRANSITIONS,
  SUPER_ADMIN_REQUIRED_TRANSITIONS,
} from "@/types/admin";
import { AdminApiError, apiUpdateEnquiryStatus } from "@/lib/admin-api";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { useModalFocusTrap } from "@/hooks/useModalFocusTrap";
import { useToast } from "@/hooks/useToast";
import { sanitizeErrorMessage } from "@/components/ui/states/StateError";

interface UpdateStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  dossier: EnquiryDetailResponseData;
  onSuccess: (updatedDossier: EnquiryDetailResponseData) => void;
}

const STATUS_LABELS: Record<string, string> = {
  NEW: "New Intake",
  UNDER_REVIEW: "Under Review",
  ASSIGNED: "Assigned",
  IN_COMMUNICATION: "In Communication",
  QUOTATION_PENDING: "Quotation Pending",
  COMPLETED: "Completed",
  DECLINED: "Declined",
  ARCHIVED: "Archived",
};

export function UpdateStatusModal({
  isOpen,
  onClose,
  dossier,
  onSuccess,
}: UpdateStatusModalProps) {
  const { csrfToken, hasRole } = useAdminAuth();
  const { toast } = useToast();
  const isSuperAdmin = hasRole("SUPER_ADMIN");

  // Permitted target transitions from current status
  const allowedTransitions = PERMITTED_STATUS_TRANSITIONS[dossier.status] || [];

  const [selectedStatus, setSelectedStatus] = useState<string>(
    allowedTransitions.length > 0 ? allowedTransitions[0] : ""
  );
  const [changeReason, setChangeReason] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Accessible focus trap, Tab navigation cycling, initial focus, Escape key listener, and focus restoration
  const modalRef = useModalFocusTrap<HTMLDivElement>({
    isOpen,
    onClose,
    initialFocusSelector: "#target-status-select",
    isSubmitting,
    preventScroll: true,
  });

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  if (!isOpen) return null;

  const transitionKey = `${dossier.status}->${selectedStatus}`;
  const requiresSuperAdmin = SUPER_ADMIN_REQUIRED_TRANSITIONS.has(transitionKey);
  const isBlockedByRole = requiresSuperAdmin && !isSuperAdmin;

  const trimmedReason = changeReason.trim();
  const isReasonValid = trimmedReason.length >= 3 && trimmedReason.length <= 1000;
  const isFormValid =
    Boolean(selectedStatus) &&
    selectedStatus !== dossier.status &&
    isReasonValid &&
    !isBlockedByRole;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || !isFormValid) return;

    if (isBlockedByRole) {
      setErrorMessage(
        `Transitioning from '${dossier.status}' to '${selectedStatus}' requires SUPER_ADMIN authority.`
      );
      return;
    }

    if (trimmedReason.length < 3) {
      setErrorMessage("Change reason must contain at least 3 non-whitespace characters.");
      return;
    }

    if (trimmedReason.length > 1000) {
      setErrorMessage("Change reason cannot exceed 1,000 characters.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const updatedDossier = await apiUpdateEnquiryStatus(
        dossier.id,
        {
          new_status: selectedStatus,
          change_reason: trimmedReason,
        },
        csrfToken,
        { signal: controller.signal }
      );

      setIsSubmitting(false);
      toast.success(`Enquiry status transitioned to ${STATUS_LABELS[selectedStatus] || selectedStatus}.`);
      onSuccess(updatedDossier);
      onClose();
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setIsSubmitting(false);

      if (err instanceof AdminApiError) {
        if (err.status === 409) {
          setErrorMessage(
            `Status conflict (409): ${sanitizeErrorMessage(err.detail || "Disallowed transition or same-status update.")}`
          );
        } else if (err.status === 403) {
          setErrorMessage(
            `Authorization failure (403): ${sanitizeErrorMessage(err.detail || "Insufficient administrative role or invalid security token.")}`
          );
        } else if (err.status === 422) {
          setErrorMessage(`Validation error (422): ${sanitizeErrorMessage(err.detail)}`);
        } else if (err.status === 404) {
          setErrorMessage("Enquiry record was not found or has been removed.");
        } else {
          setErrorMessage(sanitizeErrorMessage(err.detail || "Status transition failed. Please try again."));
        }
      } else if (err instanceof Error) {
        setErrorMessage(sanitizeErrorMessage(err.message));
      } else {
        setErrorMessage("An unexpected error occurred while updating the status.");
      }
    }
  };

  return (
    <div
      ref={modalRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="status-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs overflow-y-auto outline-hidden"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div className="relative w-full max-w-lg rounded-[2px] border border-line eb-glass shadow-xl text-ink my-8 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-line">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
              <RefreshCw className="h-4 w-4 text-brand" />
            </div>
            <div>
              <h2
                id="status-modal-title"
                className="text-sm font-heading font-bold uppercase tracking-wider text-ink"
              >
                Lifecycle Status Transition
              </h2>
              <p className="text-xs font-mono text-ink-subtle">
                Ref: {dossier.reference_number}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-[2px] text-ink-subtle hover:text-ink hover:bg-panel-2 transition-colors disabled:opacity-50 cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand"
            aria-label="Close status dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Error Banner */}
          {errorMessage && (
            <div className="p-3 rounded-[2px] bg-[#FEF2F2] dark:bg-[#2C1111] border border-[#FECACA] dark:border-[#EF4444]/40 text-xs font-mono text-[#B91C1C] dark:text-[#F87171] flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="flex-1">{errorMessage}</div>
            </div>
          )}

          {/* Current Status vs Target Status Transition Indicator */}
          <div className="p-3.5 rounded-[2px] bg-panel-2 border border-line space-y-2">
            <span className="text-[11px] uppercase tracking-wider text-ink-subtle font-mono block">
              Transition Path
            </span>
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              <span className="px-2 py-1 rounded-[2px] bg-panel-2 text-ink border border-line-strong font-semibold">
                {STATUS_LABELS[dossier.status] || dossier.status}
              </span>
              <ArrowRight className="h-3.5 w-3.5 text-ink-subtle" />
              <span className="px-2 py-1 rounded-[2px] bg-brand-soft text-brand border border-brand/40 font-semibold">
                {selectedStatus ? (STATUS_LABELS[selectedStatus] || selectedStatus) : "Select target..."}
              </span>
            </div>
          </div>

          {/* Target Status Select */}
          <div className="space-y-1.5">
            <label
              htmlFor="target-status-select"
              className="text-xs font-mono font-medium text-ink block"
            >
              Permitted Target Status
            </label>

            {allowedTransitions.length === 0 ? (
              <div className="p-3 rounded-[2px] bg-panel-2 text-xs font-mono text-ink-subtle">
                No further status transitions permitted from current status &apos;{dossier.status}&apos;.
              </div>
            ) : (
              <select
                id="target-status-select"
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                disabled={isSubmitting}
                className="w-full h-9 px-3 rounded-[2px] border border-line eb-glass text-xs font-mono text-ink focus:outline-hidden focus:border-brand transition-colors disabled:opacity-50"
              >
                {allowedTransitions.map((targetStatus) => {
                  const key = `${dossier.status}->${targetStatus}`;
                  const isRestricted = SUPER_ADMIN_REQUIRED_TRANSITIONS.has(key);
                  const label = STATUS_LABELS[targetStatus] || targetStatus;
                  return (
                    <option key={targetStatus} value={targetStatus}>
                      {label} {isRestricted ? "(Requires SUPER_ADMIN)" : ""}
                    </option>
                  );
                })}
              </select>
            )}
          </div>

          {/* Reopening Warning if transition requires SUPER_ADMIN */}
          {requiresSuperAdmin && (
            <div
              className={`p-3 rounded-[2px] border text-xs font-mono flex items-start gap-2 ${
                isSuperAdmin
                  ? "bg-[#FFFBEB] dark:bg-[#2D2312] border-[#FDE68A] dark:border-[#F59E0B]/40 text-[#B45309] dark:text-[#FBBF24]"
                  : "bg-[#FEF2F2] dark:bg-[#2C1111] border-[#FECACA] dark:border-[#EF4444]/40 text-[#B91C1C] dark:text-[#F87171]"
              }`}
            >
              <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <strong>Terminal Status Reopening:</strong> This transition moves an enquiry out of a concluded state.{" "}
                {isSuperAdmin
                  ? "Authorized as SUPER_ADMIN. Please record an explicit audit justification below."
                  : "BLOCKED: Only administrators with the SUPER_ADMIN role possess authority to reopen terminal records."}
              </div>
            </div>
          )}

          {/* Mandatory Change Reason Textarea */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono">
              <label
                htmlFor="status-change-reason"
                className="font-medium text-ink"
              >
                Change Reason <span className="text-[#B91C1C] dark:text-[#F87171]">*</span>
              </label>
              <span
                className={`text-[11px] ${
                  trimmedReason.length < 3 || trimmedReason.length > 1000
                    ? "text-[#B91C1C] dark:text-[#F87171] font-bold"
                    : "text-ink-subtle "
                }`}
              >
                {trimmedReason.length} / 1000 (min 3)
              </span>
            </div>

            <textarea
              id="status-change-reason"
              value={changeReason}
              onChange={(e) => setChangeReason(e.target.value)}
              disabled={isSubmitting}
              maxLength={1000}
              rows={3}
              placeholder="State the formal commercial reason or client communication outcome justifying this status change..."
              className="w-full p-2.5 rounded-[2px] border border-line bg-panel text-xs font-mono text-ink placeholder:text-ink-subtle focus:outline-hidden focus:border-brand transition-colors resize-y disabled:opacity-50"
            />
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-[2px] border border-line bg-panel text-xs font-mono font-medium text-ink-subtle hover:text-ink hover:border-line-strong transition-colors disabled:opacity-50 cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting || !isFormValid}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-[2px] bg-brand text-xs font-mono font-semibold text-brand-ink dark:text-[#000000] hover:bg-brand-hover dark:hover:bg-[#00D0DF] transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-brand"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Updating...</span>
                </>
              ) : (
                <>
                  <Check className="h-3.5 w-3.5" />
                  <span>Confirm Status Update</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
