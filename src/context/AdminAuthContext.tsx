"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { AdminUser, LoginCredentials, LoginResult } from "@/types/admin";
import { apiGetMe, apiLogin, apiLogout } from "@/lib/admin-api";

export interface AdminAuthContextValue {
  user: AdminUser | null;
  csrfToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<LoginResult>;
  logout: () => Promise<void>;
  hasRole: (role: string) => boolean;
  refreshSession: () => Promise<void>;
}

const AdminAuthContext = createContext<AdminAuthContextValue | undefined>(undefined);

export interface AdminAuthProviderProps {
  children: React.ReactNode;
}

export function AdminAuthProvider({ children }: AdminAuthProviderProps) {
  const [user, setUser] = useState<AdminUser | null>(null);
  // Stored strictly in React memory — never written to localStorage or cookies
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore authenticated session via GET /api/v1/auth/me on mount or browser refresh
  const restoreSession = useCallback(async () => {
    try {
      const { user: restoredUser, csrfToken: restoredToken } = await apiGetMe();
      setUser(restoredUser);
      setCsrfToken(restoredToken);
    } catch {
      // Unauthenticated, expired, or revoked session
      setUser(null);
      setCsrfToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function initSession() {
      try {
        const { user: restoredUser, csrfToken: restoredToken } = await apiGetMe();
        if (isMounted) {
          setUser(restoredUser);
          setCsrfToken(restoredToken);
        }
      } catch {
        if (isMounted) {
          setUser(null);
          setCsrfToken(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setIsLoading(true);
    try {
      const result = await apiLogin(credentials);
      // Only an administrator session populates the admin console state. A customer signing in
      // on the same page gets a customer cookie and is sent to the customer dashboard.
      if (result.accountType === "ADMIN") {
        setUser(result.user);
        setCsrfToken(result.csrfToken);
      }
      return { accountType: result.accountType, redirectTo: result.redirectTo };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await apiLogout(csrfToken);
    } finally {
      setUser(null);
      setCsrfToken(null);
      setIsLoading(false);
    }
  }, [csrfToken]);

  const hasRole = useCallback(
    (role: string): boolean => {
      if (!user || !user.roles) return false;
      return user.roles.includes(role);
    },
    [user]
  );

  const value = useMemo<AdminAuthContextValue>(
    () => ({
      user,
      csrfToken,
      isLoading,
      isAuthenticated: !!user,
      login,
      logout,
      hasRole,
      refreshSession: restoreSession,
    }),
    [user, csrfToken, isLoading, login, logout, hasRole, restoreSession]
  );

  return (
    <AdminAuthContext.Provider value={value}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth(): AdminAuthContextValue {
  const context = useContext(AdminAuthContext);
  if (!context) {
    throw new Error("useAdminAuth must be used within an AdminAuthProvider");
  }
  return context;
}
