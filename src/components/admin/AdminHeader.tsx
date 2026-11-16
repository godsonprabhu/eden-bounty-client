"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import {
  Menu,
  Sun,
  Moon,
  LogOut,
  Loader2,
  Shield,
  Activity,
} from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { useTheme } from "@/context/ThemeContext";

interface AdminHeaderProps {
  onToggleMobileNav?: () => void;
  title?: string;
}

function titleForPath(pathname: string): string {
  if (pathname.startsWith("/admin/enquiries/")) return "Enquiry Dossier";
  if (pathname.startsWith("/admin/enquiries")) return "Enquiries";
  if (pathname.startsWith("/admin/audit")) return "Audit Ledger";
  return "Console Overview";
}

export function AdminHeader({
  onToggleMobileNav,
  title,
}: AdminHeaderProps) {
  const pathname = usePathname() ?? "/admin";
  const heading = title ?? titleForPath(pathname);
  const { user, logout } = useAdminAuth();
  const { theme, toggleTheme } = useTheme();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    try {
      await logout();
      // Deliberate hard navigation to wipe all in-memory admin client state on logout
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    } catch {
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="eb-nav-glass sticky top-0 z-30 h-16 px-4 sm:px-6 flex items-center justify-between">
      {/* Left: Mobile Menu Trigger & Section Title */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleMobileNav}
          className="lg:hidden p-2 rounded-[2px] border border-line-strong text-ink-muted hover:text-ink"
          aria-label="Open mobile navigation menu"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2.5">
          <h1 className="text-sm sm:text-base font-heading font-bold tracking-tight text-ink">
            {heading}
          </h1>
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[2px] bg-panel-2 border border-line text-[10px] font-mono text-ink-subtle">
            <Activity className="h-3 w-3 text-[#10B981] animate-pulse" />
            <span>Operations Live</span>
          </span>
        </div>
      </div>

      {/* Right Controls: Theme Toggle & Logout Button */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Theme Toggle Button */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          className="p-2 rounded-[2px] border border-line-strong bg-panel-2 text-ink-muted hover:text-brand hover:border-brand transition-all cursor-pointer"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        {/* User Identity Chip (Desktop) */}
        {user && (
          <div className="hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-[2px] border border-line bg-panel-2">
            <Shield className="h-3.5 w-3.5 text-brand" />
            <span className="text-xs font-mono font-medium text-ink">
              {user.email}
            </span>
          </div>
        )}

        {/* Logout Button */}
        <button
          type="button"
          onClick={handleLogout}
          disabled={isLoggingOut}
          aria-label="Log out of console"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] border border-line-strong bg-panel-2 hover:bg-[#FEF2F2] dark:hover:bg-[#1A0A0C] text-ink-subtle hover:text-[#DC2626] dark:hover:text-[#F87171] hover:border-[#FCA5A5] dark:hover:border-[#7F1D1D] text-xs font-heading font-semibold transition-all disabled:opacity-50 cursor-pointer"
        >
          {isLoggingOut ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <LogOut className="h-3.5 w-3.5" />
          )}
          <span className="hidden sm:inline">Sign Out</span>
        </button>
      </div>
    </header>
  );
}
