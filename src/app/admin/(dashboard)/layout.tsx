"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { AdminHeader } from "@/components/admin/AdminHeader";
import { AdminMobileNav } from "@/components/admin/AdminMobileNav";
import { CorporateLogo } from "@/components/ui/CorporateLogo";
import { useTheme } from "@/context/ThemeContext";

export default function AdminDashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAdminAuth();
  const { theme } = useTheme();
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const handleOpenMobileNav = useCallback(() => setIsMobileNavOpen(true), []);
  const handleCloseMobileNav = useCallback(() => setIsMobileNavOpen(false), []);

  // Protected route enforcement
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  // Loading state during initial session restoration
  if (isLoading) {
    return (
      <div className="eb-backdrop min-h-screen flex flex-col items-center justify-center text-ink">
        <div className="flex flex-col items-center gap-4 p-8">
          <CorporateLogo
            size="lg"
            variant={theme === "dark" ? "dark" : "light"}
            withSubtitle={false}
          />
          <div className="flex items-center gap-2.5 text-xs font-mono uppercase tracking-wider text-ink-subtle">
            <Loader2 className="h-4 w-4 animate-spin text-brand" />
            <span>Restoring Administrative Session...</span>
          </div>
        </div>
      </div>
    );
  }

  // Not authenticated: render nothing while redirecting
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="eb-backdrop min-h-screen flex text-ink">
      {/* Desktop Sidebar (hidden on mobile, visible on lg) */}
      <div className="hidden lg:block w-64 shrink-0">
        <AdminSidebar className="fixed inset-y-0 left-0 w-64" />
      </div>

      {/* Mobile Off-Canvas Navigation */}
      <AdminMobileNav
        isOpen={isMobileNavOpen}
        onClose={handleCloseMobileNav}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <AdminHeader onToggleMobileNav={handleOpenMobileNav} />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          {children}
        </main>

        {/* Global Admin Institutional Footer */}
        <footer className="eb-glass-strong !border-x-0 !border-b-0 px-6 py-4 text-[11px] font-mono text-ink-subtle flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            EDEN BOUNTY Sdn. Bhd. • Company No. 202501058702 (1660108-D)
          </div>
          <div>
            Restricted Central Operations Console • Shah Alam, Selangor
          </div>
        </footer>
      </div>
    </div>
  );
}
