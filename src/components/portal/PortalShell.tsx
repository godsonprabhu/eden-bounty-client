"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Loader2, LogOut } from "lucide-react";
import { PortalAuthProvider, PORTAL_AREAS, usePortalAuth, type PortalArea } from "@/context/PortalAuthContext";
import { ThemeToggle } from "@/components/site/SiteHeader";
import { Wordmark } from "@/components/site/primitives";
import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

export interface PortalNavItem {
  title: string;
  href: string;
}

function Shell({ nav, children }: { nav: PortalNavItem[]; children: React.ReactNode }) {
  const pathname = usePathname();
  const { area, user, isLoading, logout } = usePortalAuth();
  const config = PORTAL_AREAS[area];

  if (isLoading || !user) {
    return (
      <div className="eb-backdrop flex min-h-dvh items-center justify-center text-ink">
        <p role="status" className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.2em] text-ink-subtle">
          <Loader2 className="h-4 w-4 animate-spin text-brand" aria-hidden="true" />
          {isLoading ? "Checking your session" : "Redirecting to sign in"}
        </p>
      </div>
    );
  }

  const isActive = (href: string) => (href === config.home ? pathname === href : pathname.startsWith(href));

  return (
    <div className="eb-backdrop flex min-h-dvh flex-col text-ink">
      <a href="#portal-main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[200] focus:bg-brand focus:px-4 focus:py-2 focus:text-xs focus:font-semibold focus:text-brand-ink">
        Skip to main content
      </a>
      <header className="eb-glass-strong sticky top-0 z-40 !border-x-0 !border-t-0">
        <div className="mx-auto flex min-h-16 w-full max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-8">
          <Link href="/" aria-label="EDEN BOUNTY — public website" className="shrink-0">
            <Wordmark compact />
          </Link>
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <div className="hidden min-w-0 text-right sm:block">
              <p className="truncate text-sm font-semibold text-ink">{user.full_name}</p>
              <p className="truncate font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-subtle">{config.label}</p>
            </div>
            <ThemeToggle className="h-10 w-10" />
            <button
              type="button"
              onClick={logout}
              className="inline-flex h-10 cursor-pointer items-center gap-2 border border-line-strong px-3 font-mono text-[0.66rem] uppercase tracking-[0.16em] text-ink transition-colors hover:border-brand hover:text-brand"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Log out</span>
            </button>
          </div>
        </div>
        <nav aria-label={`${config.label} sections`} className="mx-auto w-full max-w-[1200px] px-4 sm:px-8">
          <ul className="flex flex-wrap gap-x-1 border-t border-line">
            {nav.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={isActive(item.href) ? "page" : undefined}
                  className={cn(
                    "-mt-px flex min-h-11 items-center border-t-2 px-3 font-mono text-[0.66rem] uppercase tracking-[0.16em] transition-colors",
                    isActive(item.href) ? "border-brand text-ink" : "border-transparent text-ink-muted hover:text-ink"
                  )}
                >
                  {item.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main id="portal-main" className="mx-auto w-full max-w-[1200px] flex-1 space-y-8 px-4 py-8 sm:px-8 sm:py-10">
        {children}
      </main>
      <footer className="border-t border-line px-4 py-5 text-center font-mono text-[0.62rem] text-ink-subtle sm:px-8">
        {siteConfig.legalName} · Confidential — for the named account holder only ·{" "}
        <a href={`mailto:${siteConfig.contact.email}`} className="underline underline-offset-4 hover:text-brand">
          {siteConfig.contact.email}
        </a>
      </footer>
    </div>
  );
}

export function PortalShell({ area, nav, children }: { area: PortalArea; nav: PortalNavItem[]; children: React.ReactNode }) {
  return (
    <PortalAuthProvider area={area}>
      <Shell nav={nav}>{children}</Shell>
    </PortalAuthProvider>
  );
}
