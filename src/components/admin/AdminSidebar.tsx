"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Inbox,
  ShieldCheck,
  User,
  Shield, Landmark, PackageCheck, Users } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { useTheme } from "@/context/ThemeContext";
import { CorporateLogo } from "@/components/ui/CorporateLogo";
import { cn } from "@/lib/utils";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  superAdminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    name: "Overview",
    href: "/admin",
    icon: LayoutDashboard,
  },
  {
    name: "Enquiries",
    href: "/admin/enquiries",
    icon: Inbox,
  },
  {
    name: "Customers",
    href: "/admin/customers",
    icon: Users,
  },
  {
    name: "Orders",
    href: "/admin/orders",
    icon: PackageCheck,
  },
  {
    name: "Investors",
    href: "/admin/investors",
    icon: Landmark,
    superAdminOnly: true,
  },
  {
    name: "Audit Ledger",
    href: "/admin/audit",
    icon: ShieldCheck,
    superAdminOnly: true,
  },
];

export function AdminSidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const { user, hasRole } = useAdminAuth();
  const { theme } = useTheme();

  const isSuperAdmin = hasRole("SUPER_ADMIN");

  return (
    <aside
      className={cn(
        "eb-glass-strong !border-y-0 !border-l-0 flex flex-col h-full text-ink",
        className
      )}
    >
      {/* Brand & Console Title Header */}
      <div className="p-5 border-b border-line">
        <Link href="/admin" className="flex items-center gap-3 group">
          <CorporateLogo
            size="sm"
            variant={theme === "dark" ? "dark" : "light"}
            withSubtitle={false}
          />
        </Link>
        <div className="mt-2.5 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
          <span>Central Console</span>
          <span className="text-brand">v2.1.0</span>
        </div>
      </div>

      {/* Primary Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto" aria-label="Admin navigation">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-ink-subtle">
          Operations
        </div>
        {NAV_ITEMS.map((item) => {
          if (item.superAdminOnly && !isSuperAdmin) {
            return null;
          }

          const isActive =
            item.href === "/admin"
              ? pathname === "/admin"
              : pathname.startsWith(item.href);

          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-[2px] text-xs font-heading font-semibold transition-all",
                isActive
                  ? "bg-brand-soft  text-brand  border-l-2 border-brand "
                  : "text-ink-muted  hover:bg-panel-2  hover:text-ink "
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  isActive
                    ? "text-brand "
                    : "text-ink-subtle "
                )}
              />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom Administrator Profile Card */}
      {user && (
        <div className="p-4 border-t border-line bg-panel-2">
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
              <div className="mt-1.5 flex flex-wrap gap-1">
                {user.roles.map((role) => (
                  <span
                    key={role}
                    className={cn(
                      "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] text-[9px] font-mono uppercase font-semibold",
                      role === "SUPER_ADMIN"
                        ? "bg-[#FEF3C7] dark:bg-[#2A1E07] text-[#B45309] dark:text-[#FBBF24] border border-[#FDE68A] dark:border-[#78350F]"
                        : "bg-brand-soft  text-brand-hover  border border-brand/40 "
                    )}
                  >
                    <Shield className="h-2.5 w-2.5" />
                    <span>{role.replace("_", " ")}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
