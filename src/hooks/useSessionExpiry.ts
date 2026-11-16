"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useGlobalUIState } from "@/context/GlobalUIStateContext";

/**
 * Sanitizes a candidate returnUrl to ensure it is strictly a safe internal relative path under /admin.
 * Mitigates open-redirect attacks.
 */
export function sanitizeAdminReturnUrl(rawUrl: string | null | undefined): string {
  if (!rawUrl) return "/admin";
  const trimmed = rawUrl.trim();
  // Must start with /admin and NOT start with // (protocol-relative URL)
  if (
    trimmed.startsWith("/admin") &&
    !trimmed.startsWith("/admin/login") &&
    !trimmed.startsWith("//") &&
    !trimmed.includes("://")
  ) {
    return trimmed;
  }
  return "/admin";
}

export function useSessionExpiry() {
  const router = useRouter();
  const {
    isSessionExpiredOpen,
    sessionExpiredReason,
    triggerSessionExpired,
    closeSessionExpired,
  } = useGlobalUIState();

  const handleSecureLoginRedirect = useCallback(() => {
    closeSessionExpired();
    if (typeof window === "undefined") return;

    const currentPath = window.location.pathname + window.location.search;
    // Prevent redirect loops if already on login page
    if (window.location.pathname === "/login") {
      return;
    }

    const safeReturn = sanitizeAdminReturnUrl(currentPath);
    const destination = `/login?returnUrl=${encodeURIComponent(safeReturn)}`;
    router.replace(destination);
  }, [closeSessionExpired, router]);

  return {
    isSessionExpired: isSessionExpiredOpen,
    sessionExpiredReason,
    triggerSessionExpired,
    closeSessionExpired,
    handleSecureLoginRedirect,
  };
}
