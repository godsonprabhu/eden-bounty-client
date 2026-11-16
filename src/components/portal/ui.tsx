"use client";

import { useCallback, useEffect, useId, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Inbox, Loader2, RefreshCw, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useModalFocusTrap } from "@/hooks/useModalFocusTrap";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ data loading */
interface ResourceState<T> {
  key: string;
  data: T | null;
  error: string | null;
}

/** Loads one API resource and tracks loading / error state. `path` null skips loading. */
export function useResource<T>(path: string | null) {
  const [nonce, setNonce] = useState(0);
  const key = `${path}#${nonce}`;
  const [state, setState] = useState<ResourceState<T>>({ key: "", data: null, error: null });

  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal })
      .then((data) => setState({ key, data, error: null }))
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setState((prev) => ({ key, data: prev.data, error: err instanceof ApiError ? err.detail : "Unable to load this information." }));
      });
    return () => controller.abort();
  }, [path, key]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const loading = !!path && state.key !== key;
  return { data: state.data, error: state.key === key ? state.error : null, loading, reload };
}

/* ------------------------------------------------------------------ formatting */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value.toLowerCase().replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(d.getTime()) ? "—" : new Intl.DateTimeFormat("en-MY", { day: "2-digit", month: "short", year: "numeric" }).format(d);
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? "—"
    : new Intl.DateTimeFormat("en-MY", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
}

/** Formats an exact decimal string from the API. Never rounds beyond two places or converts currency. */
export function fmtMoney(amount: string | null | undefined, currency: string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return "—";
  const text = new Intl.NumberFormat("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
  return currency ? `${currency} ${text}` : text;
}

export function fmtQuantity(quantity: string | null, unit: string | null): string {
  if (!quantity) return "—";
  const n = Number(quantity);
  const text = Number.isFinite(n) ? new Intl.NumberFormat("en-MY", { maximumFractionDigits: 2 }).format(n) : quantity;
  return unit ? `${text} ${unit}` : text;
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ------------------------------------------------------------------ layout pieces */
export function PageHeader({ eyebrow, title, intro, actions }: { eyebrow?: string; title: string; intro?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="font-mono text-[0.66rem] uppercase tracking-[0.22em] text-brand">{eyebrow}</p>}
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink sm:text-3xl [overflow-wrap:anywhere]">{title}</h1>
        {intro && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">{intro}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, description, actions, children, className }: { title?: string; description?: string; actions?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border border-line bg-panel", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-ink-subtle">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Stat({ label, value, detail, href }: { label: string; value: React.ReactNode; detail?: string; href?: string }) {
  const body = (
    <>
      <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-ink-subtle">{label}</p>
      <p className="mt-3 text-2xl font-semibold tabular-nums text-ink [overflow-wrap:anywhere]">{value}</p>
      {detail && <p className="mt-1 text-xs text-ink-muted">{detail}</p>}
    </>
  );
  const cls = "block border border-line bg-panel p-5";
  return href ? (
    <Link href={href} className={cn(cls, "transition-colors hover:border-brand")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

const TONES: Record<string, string> = {
  good: "border-emerald-600/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  info: "border-brand/40 bg-brand-soft text-brand",
  warn: "border-amber-600/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  bad: "border-red-600/40 bg-red-500/10 text-red-700 dark:text-red-300",
  mute: "border-line-strong bg-panel-2 text-ink-muted",
};
const STATUS_TONE: Record<string, keyof typeof TONES> = {
  ACTIVE: "good", DELIVERED: "good", COMPLETED: "good", PUBLISHED: "good", MATURED: "good",
  CONFIRMED: "info", PROCESSING: "info", SHIPPED: "info", IN_TRANSIT: "info", OUT_FOR_DELIVERY: "info", READY_TO_SHIP: "info",
  UNDER_REVIEW: "info", ASSIGNED: "info", IN_COMMUNICATION: "info", NEW: "info",
  PENDING: "warn", INVITED: "warn", PREPARING: "warn", QUOTATION_PENDING: "warn", DRAFT: "warn", LOCKED: "warn",
  CANCELLED: "bad", DECLINED: "bad", RETURNED: "bad", INACTIVE: "bad",
  EXITED: "mute", ARCHIVED: "mute",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span className={cn("inline-flex items-center whitespace-nowrap border px-2 py-0.5 font-mono text-[0.62rem] uppercase tracking-[0.14em]", TONES[STATUS_TONE[status] ?? "mute"])}>
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-12 text-center">
      <Inbox className="h-6 w-6 text-ink-subtle" strokeWidth={1.5} aria-hidden="true" />
      <p className="text-sm font-semibold text-ink">{title}</p>
      {children && <div className="max-w-md text-sm text-ink-muted">{children}</div>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 border border-red-600/40 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300 sm:flex-row sm:items-center sm:justify-between">
      <span className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{message}</span>
      </span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="inline-flex min-h-9 cursor-pointer items-center gap-2 border border-current px-3 text-xs font-semibold uppercase tracking-wider">
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Try again
        </button>
      )}
    </div>
  );
}

export function Loading({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 animate-pulse border border-line bg-panel-2" />
      ))}
      <span className="sr-only">{label}…</span>
    </div>
  );
}

/** Wraps loading / error / empty handling around a loaded resource. */
export function Resource<T>({
  state,
  empty,
  isEmpty,
  rows,
  children,
}: {
  state: { data: T | null; error: string | null; loading: boolean; reload: () => void };
  empty?: React.ReactNode;
  isEmpty?: (data: T) => boolean;
  rows?: number;
  children: (data: T) => React.ReactNode;
}) {
  if (state.error && !state.data) return <ErrorBox message={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading rows={rows} />;
  if (empty && isEmpty?.(state.data)) return <>{empty}</>;
  return (
    <>
      {state.error && <div className="mb-4"><ErrorBox message={state.error} onRetry={state.reload} /></div>}
      {children(state.data)}
    </>
  );
}

/** Horizontally scrollable table container so wide tables never overflow the page on small screens. */
export function Table({ head, children, caption }: { head: string[]; children: React.ReactNode; caption: string }) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full min-w-[560px] border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line">
            {head.map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap py-2.5 pr-4 font-mono text-[0.62rem] font-normal uppercase tracking-[0.18em] text-ink-subtle">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}
export const td = "py-3 pr-4 align-top text-ink-muted";
export const tdStrong = "py-3 pr-4 align-top font-medium text-ink";

export function DefinitionList({ items }: { items: Array<[string, React.ReactNode]> }) {
  return (
    <dl className="divide-y divide-line">
      {items.map(([k, v]) => (
        <div key={k} className="grid gap-1 py-3 sm:grid-cols-3 sm:gap-6">
          <dt className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-subtle">{k}</dt>
          <dd className="text-sm text-ink sm:col-span-2 [overflow-wrap:anywhere]">{v || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------ form controls */
export function Button({
  variant = "primary",
  busy,
  className,
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger"; busy?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || busy}
      className={cn(
        "inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 px-4 text-xs font-semibold uppercase tracking-[0.14em] transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        variant === "primary" && "bg-brand text-brand-ink hover:bg-brand-hover",
        variant === "ghost" && "border border-line-strong text-ink hover:border-brand hover:text-brand",
        variant === "danger" && "border border-red-600/50 text-red-700 hover:bg-red-500/10 dark:text-red-300",
        className
      )}
    >
      {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

const inputCls =
  "w-full min-h-10 border border-line-strong bg-panel-2 px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand disabled:opacity-60";

type FieldElement = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
export type FieldChange = React.ChangeEvent<FieldElement>;

export function Field({
  label,
  hint,
  as = "input",
  options,
  className,
  onChange,
  ...rest
}: {
  label: string;
  hint?: string;
  as?: "input" | "textarea" | "select";
  options?: ReadonlyArray<{ value: string; label: string }>;
  className?: string;
  onChange?: (e: FieldChange) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "className">) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-subtle">
        {label}
        {rest.required && <span className="text-brand"> *</span>}
      </label>
      {as === "textarea" ? (
        <textarea
          id={id}
          aria-describedby={hintId}
          rows={4}
          {...(rest as unknown as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
          onChange={onChange}
          className={inputCls}
        />
      ) : as === "select" ? (
        <select
          id={id}
          aria-describedby={hintId}
          {...(rest as unknown as React.SelectHTMLAttributes<HTMLSelectElement>)}
          onChange={onChange}
          className={cn(inputCls, "cursor-pointer")}
        >
          {options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input id={id} aria-describedby={hintId} {...rest} onChange={onChange} className={inputCls} />
      )}
      {hint && (
        <p id={hintId} className="mt-1 text-xs text-ink-subtle">
          {hint}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ dialogs */
export function Dialog({ open, title, onClose, children, busy }: { open: boolean; title: string; onClose: () => void; children: React.ReactNode; busy?: boolean }) {
  const ref = useModalFocusTrap<HTMLDivElement>({ isOpen: open, onClose, isSubmitting: busy });
  const titleId = useId();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} className="flex max-h-[92dvh] w-full max-w-xl flex-col border border-line-strong bg-panel text-ink shadow-2xl">
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id={titleId} className="text-base font-semibold">{title}</h2>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close dialog" className="flex h-9 w-9 cursor-pointer items-center justify-center border border-line-strong text-ink-muted hover:text-ink">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} title={title} onClose={onClose} busy={busy}>
      <div className="text-sm leading-relaxed text-ink-muted">{message}</div>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} busy={busy}>{confirmLabel}</Button>
      </div>
    </Dialog>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="border border-red-600/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
      {message}
    </p>
  );
}

export function errorText(err: unknown): string {
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}
