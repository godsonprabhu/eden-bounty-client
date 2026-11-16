"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PortalMe } from "@/types/portal";

export type PortalArea = "customer" | "investor";

export const PORTAL_AREAS: Record<PortalArea, { api: string; home: string; login: string; label: string }> = {
  customer: { api: "/customer", home: "/account", login: "/login", label: "Customer account" },
  investor: { api: "/investor", home: "/investors/portal", login: "/investors/login", label: "Investor portal" },
};

interface PortalAuthValue {
  area: PortalArea;
  user: PortalMe | null;
  csrfToken: string | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const PortalAuthContext = createContext<PortalAuthValue | undefined>(undefined);

/**
 * Restores the portal session from the HttpOnly cookie by asking the API who is signed in.
 * This is a convenience for rendering only: the API authorises every request itself, so a
 * visitor who bypasses this component still receives no data.
 */
export function PortalAuthProvider({ area, children }: { area: PortalArea; children: React.ReactNode }) {
  const router = useRouter();
  const config = PORTAL_AREAS[area];
  const [user, setUser] = useState<PortalMe | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await api<PortalMe>(`${config.api}/me`));
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [config.api]);

  useEffect(() => {
    let active = true;
    api<PortalMe>(`${config.api}/me`)
      .then((me) => active && setUser(me))
      .catch(() => active && setUser(null))
      .finally(() => active && setIsLoading(false));
    return () => {
      active = false;
    };
  }, [config.api]);

  // Any API call that comes back 401 (expired, revoked or deactivated) sends the visitor to sign in.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      router.replace(config.login);
    };
    window.addEventListener("eb:portal-unauthorized", onUnauthorized);
    return () => window.removeEventListener("eb:portal-unauthorized", onUnauthorized);
  }, [config.login, router]);

  useEffect(() => {
    if (!isLoading && !user) router.replace(config.login);
  }, [isLoading, user, router, config.login]);

  const csrfToken = user?.csrf_token ?? null;
  const logout = useCallback(async () => {
    try {
      await api(`${config.api}/logout`, { method: "POST", csrf: csrfToken });
    } catch {
      /* the session may already be gone; leave regardless */
    }
    setUser(null);
    router.replace(config.login);
  }, [config.api, config.login, router, csrfToken]);

  const value = useMemo<PortalAuthValue>(
    () => ({ area, user, csrfToken, isLoading, refresh, logout }),
    [area, user, csrfToken, isLoading, refresh, logout]
  );
  return <PortalAuthContext.Provider value={value}>{children}</PortalAuthContext.Provider>;
}

export function usePortalAuth(): PortalAuthValue {
  const ctx = useContext(PortalAuthContext);
  if (!ctx) throw new Error("usePortalAuth must be used within a PortalAuthProvider");
  return ctx;
}
