"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  durationMs?: number;
  dedupKey?: string;
}

export interface GlobalUIStateContextValue {
  // Network connectivity state
  isOnline: boolean;
  wasOffline: boolean;
  reconnectedAt: Date | null;
  dismissReconnectedBanner: () => void;

  // Global Toasts system
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, "id"> & { id?: string }) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;

  // Session Expired Modal state
  isSessionExpiredOpen: boolean;
  sessionExpiredReason: string | null;
  triggerSessionExpired: (reason?: string) => void;
  closeSessionExpired: () => void;
}

const GlobalUIStateContext = createContext<GlobalUIStateContextValue | undefined>(undefined);

export interface GlobalUIStateProviderProps {
  children: React.ReactNode;
}

export function GlobalUIStateProvider({ children }: GlobalUIStateProviderProps) {
  // 1. Network connectivity tracking
  const [isOnline, setIsOnline] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return navigator.onLine;
    }
    return true;
  });
  const [wasOffline, setWasOffline] = useState<boolean>(false);
  const [reconnectedAt, setReconnectedAt] = useState<Date | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleOnline = () => {
      setIsOnline(true);
      setWasOffline(true);
      setReconnectedAt(new Date());
    };

    const handleOffline = () => {
      setIsOnline(false);
      setWasOffline(true);
      setReconnectedAt(null);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // Auto-dismiss reconnected indicator after 4 seconds
  useEffect(() => {
    if (!reconnectedAt) return;
    const timer = setTimeout(() => {
      setReconnectedAt(null);
    }, 4000);
    return () => clearTimeout(timer);
  }, [reconnectedAt]);

  const dismissReconnectedBanner = useCallback(() => {
    setReconnectedAt(null);
  }, []);

  // 2. Global Toast system with deduplication
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const recentDedupKeys = useRef<Map<string, number>>(new Map());

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (toastInput: Omit<ToastMessage, "id"> & { id?: string }): string => {
      const now = Date.now();
      const dedupKey = toastInput.dedupKey || `${toastInput.type}:${toastInput.message}`;

      // Deduplication check: drop duplicate toast within 3 seconds
      const lastFired = recentDedupKeys.current.get(dedupKey);
      if (lastFired && now - lastFired < 3000) {
        return "";
      }
      recentDedupKeys.current.set(dedupKey, now);

      const id = toastInput.id || `toast-${now}-${Math.random().toString(36).substring(2, 7)}`;
      const duration = toastInput.durationMs ?? (toastInput.type === "error" ? 8000 : 5000);

      const newToast: ToastMessage = {
        id,
        type: toastInput.type,
        title: toastInput.title,
        message: toastInput.message,
        durationMs: duration,
        dedupKey,
      };

      setToasts((prev) => [...prev.slice(-4), newToast]); // Keep maximum 5 active toasts

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }

      return id;
    },
    [removeToast]
  );

  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  // 3. Session Expired Modal state
  const [isSessionExpiredOpen, setIsSessionExpiredOpen] = useState<boolean>(false);
  const [sessionExpiredReason, setSessionExpiredReason] = useState<string | null>(null);

  const triggerSessionExpired = useCallback((reason?: string) => {
    setSessionExpiredReason(reason || "Your administrative security session has expired.");
    setIsSessionExpiredOpen(true);
  }, []);

  const closeSessionExpired = useCallback(() => {
    setIsSessionExpiredOpen(false);
    setSessionExpiredReason(null);
  }, []);

  // Listen to custom window event 'eb:session-expired'
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleSessionExpiredEvent = (e: Event) => {
      const customEvent = e as CustomEvent<{ reason?: string }>;
      triggerSessionExpired(customEvent.detail?.reason);
    };

    window.addEventListener("eb:session-expired", handleSessionExpiredEvent);
    return () => {
      window.removeEventListener("eb:session-expired", handleSessionExpiredEvent);
    };
  }, [triggerSessionExpired]);

  const value = useMemo<GlobalUIStateContextValue>(
    () => ({
      isOnline,
      wasOffline,
      reconnectedAt,
      dismissReconnectedBanner,
      toasts,
      addToast,
      removeToast,
      clearToasts,
      isSessionExpiredOpen,
      sessionExpiredReason,
      triggerSessionExpired,
      closeSessionExpired,
    }),
    [
      isOnline,
      wasOffline,
      reconnectedAt,
      dismissReconnectedBanner,
      toasts,
      addToast,
      removeToast,
      clearToasts,
      isSessionExpiredOpen,
      sessionExpiredReason,
      triggerSessionExpired,
      closeSessionExpired,
    ]
  );

  return (
    <GlobalUIStateContext.Provider value={value}>
      {children}
    </GlobalUIStateContext.Provider>
  );
}

export function useGlobalUIState(): GlobalUIStateContextValue {
  const context = useContext(GlobalUIStateContext);
  if (!context) {
    throw new Error("useGlobalUIState must be used within a GlobalUIStateProvider");
  }
  return context;
}
