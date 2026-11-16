"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  Lock,
  RefreshCw,
  UserCheck,
  X,
} from "lucide-react";
import {
  AdminAssigneeSummary,
  EnquiryDetailResponseData,
} from "@/types/admin";
import { AdminApiError, apiAssignEnquiry, apiGetAdministrators } from "@/lib/admin-api";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { useModalFocusTrap } from "@/hooks/useModalFocusTrap";
import { useToast } from "@/hooks/useToast";
import { sanitizeErrorMessage } from "@/components/ui/states/StateError";

interface AssignEnquiryModalProps {
  isOpen: boolean;
  onClose: () => void;
  dossier: EnquiryDetailResponseData;
  onSuccess: (updatedDossier: EnquiryDetailResponseData) => void;
}

export function AssignEnquiryModal({
  isOpen,
  onClose,
  dossier,
  onSuccess,
}: AssignEnquiryModalProps) {
  const { csrfToken } = useAdminAuth();
  const { toast } = useToast();

  const [assignees, setAssignees] = useState<AdminAssigneeSummary[]>([]);
  const [isLoadingAssignees, setIsLoadingAssignees] = useState<boolean>(true);
  const [selectedAdminId, setSelectedAdminId] = useState<string>(
    dossier.assigned_admin?.id ?? ""
  );
  const [rationale, setRationale] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Accessible focus trap, Tab navigation cycling, initial focus, Escape key listener, and focus restoration
  const modalRef = useModalFocusTrap<HTMLDivElement>({
    isOpen,
    onClose,
    initialFocusSelector: "#target-admin-select",
    isLoading: isLoadingAssignees,
    isSubmitting,
    preventScroll: true,
  });

  // Fetch active administrators on mount
  useEffect(() => {
    let isMounted = true;

    apiGetAdministrators()
      .then((data) => {
        if (isMounted) {
          setAssignees(data);
          setIsLoadingAssignees(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setIsLoadingAssignees(false);
          setErrorMessage(
            err instanceof Error
              ? err.message
              : "Unable to load administrator directory"
          );
        }
      });

    return () => {
      isMounted = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  if (!isOpen) return null;

  const currentAdminId = dossier.assigned_admin?.id ?? "";
  const isUnassigning = selectedAdminId === "" && currentAdminId !== "";
  const isReassigning =
    selectedAdminId !== "" &&
    currentAdminId !== "" &&
    selectedAdminId !== currentAdminId;
  const isNewAssignment = selectedAdminId !== "" && currentAdminId === "";
  const isUnchanged = selectedAdminId === currentAdminId && !rationale.trim();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (rationale.length > 1000) {
      setErrorMessage("Assignment rationale cannot exceed 1,000 characters.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const targetAdminId = selectedAdminId.trim() ? selectedAdminId.trim() : null;
      const updatedDossier = await apiAssignEnquiry(
        dossier.id,
        {
          assigned_admin_id: targetAdminId,
          assignment_rationale: rationale.trim() || null,
        },
        csrfToken,
        { signal: controller.signal }
      );

      setIsSubmitting(false);
      toast.success("Enquiry assignment updated successfully.");
      onSuccess(updatedDossier);
      onClose();
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setIsSubmitting(false);

      if (err instanceof AdminApiError) {
        if (err.status === 403) {
          setErrorMessage(
            "Authorization failed: Insufficient permissions or CSRF token expired. Please refresh the page."
          );
        } else if (err.status === 400) {
          setErrorMessage(`Invalid assignment request: ${sanitizeErrorMessage(err.detail)}`);
        } else if (err.status === 404) {
          setErrorMessage("Enquiry record was not found or has been removed.");
        } else {
          setErrorMessage(sanitizeErrorMessage(err.detail || "Assignment update failed. Please try again."));
        }
      } else if (err instanceof Error) {
        setErrorMessage(sanitizeErrorMessage(err.message));
      } else {
        setErrorMessage("An unexpected error occurred while assigning the enquiry.");
      }
    }
  };

  return (
    <div
      ref={modalRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="assign-modal-title"
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
              <UserCheck className="h-4 w-4 text-brand" />
            </div>
            <div>
              <h2
                id="assign-modal-title"
                className="text-sm font-heading font-bold uppercase tracking-wider text-ink"
              >
                Routing & Assignment
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
            aria-label="Close assignment dialog"
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

          {/* Division Lock Invariant */}
          <div className="p-3 rounded-[2px] bg-panel-2 border border-line flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2">
              <Lock className="h-3.5 w-3.5 text-ink-subtle" />
              <span className="text-ink-subtle">Commercial Division:</span>
              <span className="font-semibold text-ink">
                {dossier.current_division.name}
              </span>
            </div>
            <span className="text-[10px] px-1.5 py-0.5 rounded-[2px] bg-panel-2 text-ink-muted border border-line-strong">
              Division Locked
            </span>
          </div>

          {/* Current Assignee Card */}
          <div className="p-3 rounded-[2px] bg-panel-2 border border-line text-xs font-mono space-y-1">
            <span className="text-[11px] uppercase tracking-wider text-ink-subtle block">
              Current Assignment
            </span>
            <div className="flex items-center justify-between">
              {dossier.assigned_admin ? (
                <div className="flex items-center gap-2">
                  <span className="font-medium text-ink">
                    {dossier.assigned_admin.name}
                  </span>
                  <span className="text-[11px] text-ink-subtle">
                    ({dossier.assigned_admin.email})
                  </span>
                </div>
              ) : (
                <span className="text-ink-subtle italic">
                  Currently Unassigned (Central Pool)
                </span>
              )}
            </div>
          </div>

          {/* Target Administrator Selector */}
          <div className="space-y-1.5">
            <label
              htmlFor="target-admin-select"
              className="text-xs font-mono font-medium text-ink flex items-center justify-between"
            >
              <span>Assign To Administrator</span>
              {isLoadingAssignees && (
                <span className="text-[11px] text-brand flex items-center gap-1 font-normal">
                  <RefreshCw className="h-3 w-3 animate-spin" /> Loading directory...
                </span>
              )}
            </label>

            <select
              id="target-admin-select"
              value={selectedAdminId}
              onChange={(e) => setSelectedAdminId(e.target.value)}
              disabled={isSubmitting || isLoadingAssignees}
              className="w-full h-9 px-3 rounded-[2px] border border-line eb-glass text-xs font-mono text-ink focus:outline-hidden focus:border-brand transition-colors disabled:opacity-50"
            >
              <option value="">-- Unassign (Return to Central Pool) --</option>
              {assignees.map((admin) => (
                <option key={admin.id} value={admin.id}>
                  {admin.first_name} {admin.last_name}{" "}
                  {admin.job_title ? `(${admin.job_title})` : ""} — {admin.email}
                </option>
              ))}
            </select>
          </div>

          {/* Auto-Transition Notice if enquiry is in NEW status */}
          {dossier.status === "NEW" && selectedAdminId !== "" && (
            <div className="p-2.5 rounded-[2px] bg-[#EFF6FF] border border-[#BFDBFE] dark:border-[#3B82F6]/40 text-xs font-mono text-[#1D4ED8] dark:text-[#60A5FA]">
              Note: Assigning this enquiry from <strong>NEW</strong> status will automatically transition it to <strong>ASSIGNED</strong>.
            </div>
          )}

          {/* Assignment Rationale Textarea */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono">
              <label
                htmlFor="assignment-rationale"
                className="font-medium text-ink"
              >
                Assignment Rationale (Optional)
              </label>
              <span
                className={`text-[11px] ${
                  rationale.length > 1000
                    ? "text-[#B91C1C] dark:text-[#F87171] font-bold"
                    : "text-ink-subtle "
                }`}
              >
                {rationale.length} / 1000
              </span>
            </div>

            <textarea
              id="assignment-rationale"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              disabled={isSubmitting}
              maxLength={1000}
              rows={3}
              placeholder="Provide commercial context, specialty desk requirements, or transfer justification..."
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
              disabled={isSubmitting || isUnchanged}
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
                  <span>
                    {isUnassigning
                      ? "Confirm Unassign"
                      : isReassigning
                      ? "Confirm Reassign"
                      : isNewAssignment
                      ? "Confirm Assign"
                      : "Save Assignment"}
                  </span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
