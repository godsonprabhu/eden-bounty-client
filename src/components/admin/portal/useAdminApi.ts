"use client";

import { useCallback } from "react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { api, type ApiOptions } from "@/lib/api";

/** Sends state-changing admin requests with the current session's CSRF token. */
export function useAdminApi() {
  const { csrfToken, hasRole } = useAdminAuth();
  const send = useCallback(
    <T,>(path: string, method: NonNullable<ApiOptions["method"]>, body?: unknown, extra?: Pick<ApiOptions, "raw" | "contentType">) =>
      api<T>(path, { method, body, csrf: csrfToken, ...extra }),
    [csrfToken]
  );
  return { send, isSuperAdmin: hasRole("SUPER_ADMIN") };
}
