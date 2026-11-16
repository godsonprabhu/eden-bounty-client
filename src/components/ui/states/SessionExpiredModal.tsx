"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldAlert, LogIn, ExternalLink } from "lucide-react";
import { useSessionExpiry } from "@/hooks/useSessionExpiry";
import { useModalFocusTrap } from "@/hooks/useModalFocusTrap";
import { useGlobalUIState } from "@/context/GlobalUIStateContext";

export function SessionExpiredModal() {
  const { isSessionExpired, sessionExpiredReason, handleSecureLoginRedirect } = useSessionExpiry();
  const { closeSessionExpired } = useGlobalUIState();
  const onLoginPage = usePathname() === "/login";

  // The sign-in page already is the recovery path: clear any pending expiry notice there,
  // so it neither covers the form nor reappears after a successful sign-in.
  useEffect(() => {
    if (onLoginPage && isSessionExpired) closeSessionExpired();
  }, [onLoginPage, isSessionExpired, closeSessionExpired]);

  const containerRef = useModalFocusTrap<HTMLDivElement>({
    isOpen: isSessionExpired && !onLoginPage,
    onClose: handleSecureLoginRedirect,
  });

  if (!isSessionExpired || onLoginPage) {
    return null;
  }

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-expired-title"
        aria-describedby="session-expired-desc"
        className="w-full max-w-md rounded-[2px] border border-line-strong bg-panel p-6 shadow-2xl space-y-5 text-ink"
      >
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[2px] bg-[#FEF2F2] dark:bg-[#2D0D11] border border-[#FCA5A5] dark:border-[#7F1D1D] text-[#DC2626] dark:text-[#EF4444]">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div className="space-y-1 min-w-0">
            <h2
              id="session-expired-title"
              className="font-heading text-base font-bold text-ink uppercase tracking-wide"
            >
              Session Expired
            </h2>
            <p
              id="session-expired-desc"
              className="text-xs font-body text-ink-muted leading-relaxed"
            >
              {sessionExpiredReason ||
                "Your administrative security session has timed out or been invalidated. To protect institutional commercial records, re-authentication is required."}
            </p>
          </div>
        </div>

        <div className="rounded-[2px] border border-line bg-panel-2 p-3 text-[11px] font-mono text-ink-subtle space-y-1">
          <div className="font-semibold uppercase tracking-wider text-brand">
            Authority Context:
          </div>
          <div>
            EDEN BOUNTY Single Administrator Console • SUPER_ADMIN authority required to resume operational workflows.
          </div>
        </div>

        <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2.5 pt-2">
          <Link
            href="/"
            className="inline-flex min-h-[44px] items-center justify-center gap-1.5 px-4 py-2 rounded-[2px] border border-line-strong font-heading text-xs font-semibold uppercase tracking-wider text-ink-muted hover:bg-panel-2 transition-colors cursor-pointer text-center"
          >
            <span>Exit to Public Site</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
          <button
            type="button"
            onClick={handleSecureLoginRedirect}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 px-5 py-2 rounded-[2px] bg-brand font-heading text-xs font-semibold uppercase tracking-wider text-brand-ink hover:bg-brand-hover transition-all cursor-pointer shadow-sm"
          >
            <LogIn className="h-4 w-4" />
            <span>Log In Again</span>
          </button>
        </div>
      </div>
    </div>
  );
}
