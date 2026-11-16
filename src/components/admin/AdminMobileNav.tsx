"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  X,
  LayoutDashboard,
  Inbox,
  ShieldCheck,
  User,
  Shield,
  LogOut,
  Sun,
  Moon, Landmark, PackageCheck, Users } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { useTheme } from "@/context/ThemeContext";
import { CorporateLogo } from "@/components/ui/CorporateLogo";
import { cn } from "@/lib/utils";

interface AdminMobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AdminMobileNav({ isOpen, onClose }: AdminMobileNavProps) {
  const pathname = usePathname();
  const { user, hasRole, logout } = useAdminAuth();
  const { theme, toggleTheme } = useTheme();

  // Close drawer on route change
  const prevPathname = useRef(pathname);
  useEffect(() => {
    if (prevPathname.current !== pathname) {
      prevPathname.current = pathname;
      onClose();
    }
  }, [pathname, onClose]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const isSuperAdmin = hasRole("SUPER_ADMIN");

  const handleLogout = async () => {
    onClose();
    await logout();
    // Deliberate hard navigation to wipe all in-memory admin client state on logout
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  };

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Mobile Navigation">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-[#000000]/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Drawer */}
      <div className="eb-glass-strong !border-y-0 !border-l-0 fixed inset-y-0 left-0 w-full max-w-xs flex flex-col justify-between">
        {/* Drawer Header */}
        <div>
          <div className="p-4 flex items-center justify-between border-b border-line">
            <CorporateLogo
              size="sm"
              variant={theme === "dark" ? "dark" : "light"}
              withSubtitle={false}
            />
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-[2px] border border-line-strong text-ink-muted"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
              Operations
            </div>

            <Link
              href="/admin"
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                pathname === "/admin"
                  ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                  : "text-ink-muted  hover:bg-panel-2 "
              )}
            >
              <LayoutDashboard className="h-4 w-4" />
              <span>Overview</span>
            </Link>

            <Link
              href="/admin/enquiries"
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                pathname.startsWith("/admin/enquiries")
                  ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                  : "text-ink-muted  hover:bg-panel-2 "
              )}
            >
              <Inbox className="h-4 w-4" />
              <span>Enquiries</span>
            </Link>

            <Link
              href="/admin/customers"
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                pathname.startsWith("/admin/customers")
                  ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                  : "text-ink-muted  hover:bg-panel-2 "
              )}
            >
              <Users className="h-4 w-4" />
              <span>Customers</span>
            </Link>

            <Link
              href="/admin/orders"
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                pathname.startsWith("/admin/orders")
                  ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                  : "text-ink-muted  hover:bg-panel-2 "
              )}
            >
              <PackageCheck className="h-4 w-4" />
              <span>Orders</span>
            </Link>

            {isSuperAdmin && (
            <Link
              href="/admin/investors"
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                pathname.startsWith("/admin/investors")
                  ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                  : "text-ink-muted  hover:bg-panel-2 "
              )}
            >
              <Landmark className="h-4 w-4" />
              <span>Investors</span>
            </Link>
            )}

            {isSuperAdmin && (
              <Link
                href="/admin/audit"
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                  pathname.startsWith("/admin/audit")
                    ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                    : "text-ink-muted  hover:bg-panel-2 "
                )}
              >
                <ShieldCheck className="h-4 w-4" />
                <span>Audit Ledger</span>
              </Link>
            )}
          </nav>
        </div>

        {/* Drawer Footer with User Details & Controls */}
        <div className="p-4 border-t border-line bg-panel-2 space-y-4">
          {user && (
            <div className="flex items-start gap-3">
              <div className="h-8 w-8 rounded-[2px] bg-line flex items-center justify-center shrink-0 border border-line-strong">
                <User className="h-4 w-4 text-brand" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-heading font-bold text-ink truncate">
                  {user.first_name} {user.last_name}
                </p>
                <p className="text-[11px] font-mono text-ink-subtle truncate">
                  {user.email}
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {user.roles.map((role) => (
                    <span
                      key={role}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] text-[9px] font-mono uppercase font-semibold bg-brand-soft text-brand-hover"
                    >
                      <Shield className="h-2.5 w-2.5" />
                      <span>{role.replace("_", " ")}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-line">
            <button
              type="button"
              onClick={toggleTheme}
              className="inline-flex items-center gap-2 text-xs font-mono text-ink-muted"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] border border-line-strong text-xs font-heading font-semibold text-[#DC2626] dark:text-[#F87171]"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
