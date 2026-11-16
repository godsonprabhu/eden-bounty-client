"use client";

import { useCallback } from "react";
import { useGlobalUIState } from "@/context/GlobalUIStateContext";

export function useToast() {
  const { addToast, removeToast, clearToasts, toasts } = useGlobalUIState();

  const success = useCallback(
    (message: string, options?: { title?: string; durationMs?: number; dedupKey?: string }) => {
      return addToast({
        type: "success",
        message,
        title: options?.title || "Operation Successful",
        durationMs: options?.durationMs,
        dedupKey: options?.dedupKey,
      });
    },
    [addToast]
  );

  const error = useCallback(
    (message: string, options?: { title?: string; durationMs?: number; dedupKey?: string }) => {
      return addToast({
        type: "error",
        message,
        title: options?.title || "System Error",
        durationMs: options?.durationMs,
        dedupKey: options?.dedupKey,
      });
    },
    [addToast]
  );

  const warning = useCallback(
    (message: string, options?: { title?: string; durationMs?: number; dedupKey?: string }) => {
      return addToast({
        type: "warning",
        message,
        title: options?.title || "Attention Required",
        durationMs: options?.durationMs,
        dedupKey: options?.dedupKey,
      });
    },
    [addToast]
  );

  const info = useCallback(
    (message: string, options?: { title?: string; durationMs?: number; dedupKey?: string }) => {
      return addToast({
        type: "info",
        message,
        title: options?.title || "Notice",
        durationMs: options?.durationMs,
        dedupKey: options?.dedupKey,
      });
    },
    [addToast]
  );

  return {
    toasts,
    toast: {
      success,
      error,
      warning,
      info,
    },
    removeToast,
    clearToasts,
  };
}
