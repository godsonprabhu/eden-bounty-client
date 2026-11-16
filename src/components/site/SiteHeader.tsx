"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowRight, ArrowUpRight, ChevronDown, Menu, Moon, Sun, X } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { useScrolled } from "@/hooks/useScrolled";
import { useModalFocusTrap } from "@/hooks/useModalFocusTrap";
import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";
import { EASE, Wordmark } from "./primitives";
import { SITE_ACTIONS, SITE_MENU, type NavMenuItem } from "./nav";


export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light ocean theme" : "Switch to dark cinematic theme"}
      suppressHydrationWarning
      className={cn(
        "relative flex h-11 w-11 cursor-pointer items-center justify-center border border-line-strong text-ink transition-colors duration-300 hover:border-brand hover:text-brand",
        className
      )}
    >
      <Sun className="hidden h-[17px] w-[17px] dark:block" aria-hidden="true" />
      <Moon className="block h-[17px] w-[17px] dark:hidden" aria-hidden="true" />
    </button>
  );
}

const CLOSE_DELAY_MS = 140;

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

/** Desktop mega-menu panel for one top-level item. */
function MegaPanel({ item, panelId, onNavigate }: { item: NavMenuItem; panelId: string; onNavigate: () => void }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      id={panelId}
      role="region"
      aria-label={`${item.title} menu`}
      className="eb-glass-strong absolute inset-x-0 top-full !border-x-0 !bg-paper/[0.97] shadow-[0_30px_60px_-30px_rgba(0,0,0,0.45)]"
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6, transition: { duration: 0.16 } }}
      transition={{ duration: 0.28, ease: EASE }}
    >
      {/* Keyed by item: moving between menus swaps the content with a quick fade while the panel stays open. */}
      <motion.div
        key={item.title}
        className="mx-auto grid w-full max-w-[1380px] gap-10 px-4 py-10 sm:px-8 lg:px-12 xl:grid-cols-12"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduce ? 0 : 0.2, ease: EASE }}
      >
        <div className="xl:col-span-3">
          <p className="eb-eyebrow">
            <span className="text-brand">{item.index}</span> — {item.title}
          </p>
          <p className="mt-5 text-sm leading-relaxed text-ink-muted">{item.intro}</p>
          <Link
            href={item.href}
            onClick={onNavigate}
            className="group mt-6 inline-flex min-h-11 items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.2em] text-ink underline decoration-brand underline-offset-8 hover:text-brand"
          >
            Go to {item.title}
            <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" aria-hidden="true" />
          </Link>
        </div>
        <div
          className="grid gap-x-8 gap-y-8 border-line xl:col-span-9 xl:border-l xl:pl-10"
          style={{ gridTemplateColumns: `repeat(${item.columns?.length ?? 1}, minmax(0, 1fr))` }}
        >
          {item.columns?.map((col, ci) => (
            <div key={`${col.heading}-${ci}`}>
              <p className="font-mono text-[0.6rem] uppercase tracking-[0.22em] text-ink-subtle">{col.heading}</p>
              <ul className="mt-4 space-y-1">
                {col.links.map((link) => (
                  <li key={link.href + link.title}>
                    <Link
                      href={link.href}
                      onClick={onNavigate}
                      className="group -mx-3 block px-3 py-2.5 transition-colors duration-200 hover:bg-ink/5 focus-visible:bg-ink/5"
                    >
                      <span className="flex items-center gap-2 text-sm font-semibold text-ink transition-colors group-hover:text-brand">
                        {link.title}
                        <ArrowUpRight className="h-3.5 w-3.5 -translate-x-1 opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-100" aria-hidden="true" />
                      </span>
                      {link.description && <span className="mt-0.5 block text-xs text-ink-subtle">{link.description}</span>}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const scrolled = useScrolled(24);
  const reduce = useReducedMotion();
  const uid = useId();

  // Mobile sheet remembers the path it was opened on, so any navigation closes it.
  const [openPath, setOpenPath] = useState<string | null>(null);
  const open = openPath === pathname;
  const setOpen = (v: boolean | ((prev: boolean) => boolean)) =>
    setOpenPath((prev) => {
      const next = typeof v === "function" ? v(prev === pathname) : v;
      return next ? pathname : null;
    });
  const sheetRef = useModalFocusTrap<HTMLDivElement>({ isOpen: open, onClose: () => setOpen(false) });
  const [mobileSection, setMobileSection] = useState<string | null>(null);

  // Desktop mega menu: which top-level item is open (also tied to the path, so navigation closes it).
  const [menu, setMenu] = useState<{ title: string; path: string } | null>(null);
  const activeMenu = menu && menu.path === pathname ? menu.title : null;
  const headerRef = useRef<HTMLElement>(null);
  const closeTimer = useRef<number | null>(null);
  const triggerRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const cancelClose = useCallback(() => {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);
  const openMenu = useCallback(
    (title: string) => {
      cancelClose();
      setMenu({ title, path: pathname });
    },
    [cancelClose, pathname]
  );
  const closeMenu = useCallback(() => {
    cancelClose();
    setMenu(null);
  }, [cancelClose]);
  const scheduleClose = useCallback(() => {
    cancelClose();
    closeTimer.current = window.setTimeout(() => setMenu(null), CLOSE_DELAY_MS);
  }, [cancelClose]);

  // Close on outside click/tap and on Escape (returning focus to the trigger).
  useEffect(() => {
    if (!activeMenu) return;
    const onPointerDown = (e: PointerEvent) => {
      if (headerRef.current && !headerRef.current.contains(e.target as Node)) closeMenu();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        const trigger = triggerRefs.current[activeMenu];
        closeMenu();
        trigger?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [activeMenu, closeMenu]);

  useEffect(() => cancelClose, [cancelClose]);

  const activeItem = SITE_MENU.find((m) => m.title === activeMenu && m.columns);

  return (
    <header
      ref={headerRef}
      onBlur={(e) => {
        // Keyboard focus left the header entirely: close the panel.
        if (activeMenu && !e.currentTarget.contains(e.relatedTarget as Node | null)) closeMenu();
      }}
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-500",
        scrolled || open || activeMenu ? "eb-nav-glass" : "border-b border-transparent bg-transparent"
      )}
    >
      <div className="mx-auto flex h-[72px] w-full max-w-[1380px] items-center justify-between gap-6 px-4 sm:px-8 lg:px-12">
        <Link href="/" aria-label="EDEN BOUNTY — home" className="shrink-0">
          <Wordmark />
        </Link>

        <nav aria-label="Primary" className="hidden xl:block">
          <ul className="flex items-center gap-1">
            {SITE_MENU.map((item) => {
              const active = isActivePath(pathname, item.href);
              const hasPanel = !!item.columns;
              const expanded = activeMenu === item.title;
              const panelId = `${uid}-panel-${item.index}`;
              return (
                <li
                  key={item.href}
                  className="relative flex items-center"
                  onPointerEnter={(e) => {
                    if (e.pointerType !== "mouse") return;
                    if (hasPanel) openMenu(item.title);
                    else closeMenu();
                  }}
                  onPointerLeave={(e) => {
                    if (e.pointerType === "mouse" && hasPanel) scheduleClose();
                  }}
                >
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    onClick={closeMenu}
                    className={cn(
                      "relative flex h-11 items-center font-mono text-[0.7rem] uppercase tracking-[0.2em] transition-colors duration-300",
                      hasPanel ? "pl-3.5 pr-1" : "px-3.5",
                      active || expanded ? "text-ink" : "text-ink-muted hover:text-ink"
                    )}
                  >
                    {item.title}
                    {active && (
                      <motion.span
                        layoutId="nav-active"
                        className={cn("absolute -bottom-px left-3.5 h-px bg-brand", hasPanel ? "right-1" : "right-3.5")}
                        transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 34 }}
                      />
                    )}
                  </Link>
                  {hasPanel && (
                    <button
                      type="button"
                      ref={(el) => {
                        triggerRefs.current[item.title] = el;
                      }}
                      aria-expanded={expanded}
                      aria-controls={panelId}
                      aria-label={`${expanded ? "Close" : "Open"} ${item.title} menu`}
                      onClick={() => (expanded ? closeMenu() : openMenu(item.title))}
                      onKeyDown={(e) => {
                        if (e.key === "ArrowDown") {
                          e.preventDefault();
                          openMenu(item.title);
                          window.requestAnimationFrame(() =>
                            document.getElementById(panelId)?.querySelector<HTMLAnchorElement>("a[href]")?.focus()
                          );
                        }
                      }}
                      className={cn(
                        "flex h-11 w-7 cursor-pointer items-center justify-center transition-colors duration-300",
                        expanded ? "text-brand" : "text-ink-subtle hover:text-ink"
                      )}
                    >
                      <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-300", expanded && "rotate-180")} aria-hidden="true" />
                    </button>
                  )}
                </li>
              );
            })}
            {SITE_ACTIONS.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <li key={item.title} className={item.variant === "outline" ? "ml-3" : "ml-2"} onPointerEnter={closeMenu}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group inline-flex h-11 items-center gap-2 px-5 font-mono text-[0.7rem] uppercase tracking-[0.2em] transition-[background-color,color,border-color,box-shadow] duration-300",
                      item.variant === "outline"
                        ? cn("border text-ink hover:border-brand hover:text-brand", active ? "border-brand text-brand" : "border-line-strong")
                        : "bg-brand font-semibold text-brand-ink shadow-[0_10px_40px_-14px_var(--eb-glow)] hover:bg-brand-hover"
                    )}
                  >
                    {item.title}
                    {item.variant === "primary" && (
                      <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            type="button"
            className="flex h-11 w-11 cursor-pointer items-center justify-center border border-line-strong text-ink xl:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="site-mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
          </button>
        </div>
      </div>

      {/* Desktop mega-menu panel */}
      <div className="hidden xl:block" onPointerEnter={cancelClose} onPointerLeave={(e) => e.pointerType === "mouse" && scheduleClose()}>
        <AnimatePresence>
          {activeItem && (
            <MegaPanel key="mega-panel" item={activeItem} panelId={`${uid}-panel-${activeItem.index}`} onNavigate={closeMenu} />
          )}
        </AnimatePresence>
      </div>

      {/* Mobile / tablet sheet with tap-to-open accordion */}
      <AnimatePresence>
        {open && (
          <motion.div
            ref={sheetRef}
            id="site-mobile-nav"
            role="dialog"
            aria-modal="true"
            aria-label="Site navigation"
            className="eb-glass-strong fixed inset-x-0 bottom-0 top-[72px] z-40 flex flex-col justify-between overflow-y-auto overflow-x-hidden px-4 pb-10 pt-6 sm:px-8 xl:hidden"
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.2 } }}
            transition={{ duration: 0.45, ease: EASE }}
          >
            <ul>
              {SITE_MENU.map((item, i) => {
                const active = isActivePath(pathname, item.href);
                const expanded = mobileSection === item.title;
                const sectionId = `${uid}-m-${item.index}`;
                return (
                  <motion.li
                    key={item.href}
                    className="border-b border-line"
                    initial={reduce ? false : { opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.05 + i * 0.05, ease: EASE }}
                  >
                    <div className="flex items-stretch">
                      <Link
                        href={item.href}
                        onClick={() => setOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className="flex min-w-0 flex-1 items-baseline py-4"
                      >
                        <span className={cn("eb-display text-4xl", active ? "text-ink" : "text-ink-muted")}>{item.title}</span>
                      </Link>
                      {item.columns && (
                        <button
                          type="button"
                          aria-expanded={expanded}
                          aria-controls={sectionId}
                          aria-label={`${expanded ? "Collapse" : "Expand"} ${item.title} links`}
                          onClick={() => setMobileSection(expanded ? null : item.title)}
                          className="flex w-14 shrink-0 cursor-pointer items-center justify-center border-l border-line text-ink"
                        >
                          <ChevronDown className={cn("h-5 w-5 transition-transform duration-300", expanded && "rotate-180 text-brand")} aria-hidden="true" />
                        </button>
                      )}
                    </div>
                    <AnimatePresence initial={false}>
                      {item.columns && expanded && (
                        <motion.div
                          id={sectionId}
                          className="overflow-hidden"
                          initial={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
                          animate={reduce ? { opacity: 1 } : { height: "auto", opacity: 1 }}
                          exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
                          transition={{ duration: 0.3, ease: EASE }}
                        >
                          <ul className="grid gap-x-6 pb-5 pl-8 sm:grid-cols-2">
                            {item.columns
                              .flatMap((c) => c.links)
                              .map((link) => (
                                <li key={link.href + link.title}>
                                  <Link
                                    href={link.href}
                                    onClick={() => setOpen(false)}
                                    className="flex min-h-11 items-center gap-2 text-sm text-ink-muted transition-colors hover:text-brand"
                                  >
                                    <span className="h-px w-3 shrink-0 bg-brand" aria-hidden="true" />
                                    <span className="min-w-0 break-words">{link.title}</span>
                                  </Link>
                                </li>
                              ))}
                          </ul>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.li>
                );
              })}
            </ul>
            <div className="mt-8 grid grid-cols-2 gap-3">
              {SITE_ACTIONS.map((item) => (
                <Link
                  key={item.title}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={isActivePath(pathname, item.href) ? "page" : undefined}
                  className={cn(
                    "flex min-h-12 items-center justify-center gap-2 font-mono text-xs uppercase tracking-[0.2em]",
                    item.variant === "outline"
                      ? cn("border text-ink", isActivePath(pathname, item.href) ? "border-brand text-brand" : "border-line-strong")
                      : "bg-brand font-semibold text-brand-ink"
                  )}
                >
                  {item.title}
                </Link>
              ))}
            </div>
            <div className="mt-10 space-y-2 font-mono text-xs text-ink-subtle">
              <a href={`mailto:${siteConfig.contact.email}`} className="block text-ink [overflow-wrap:anywhere]">
                {siteConfig.contact.email}
              </a>
              <p>Shah Alam, Selangor · UTC+8</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
