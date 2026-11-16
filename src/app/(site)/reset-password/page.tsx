"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, Eye, EyeOff, Loader2, Lock } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { AuthAlert, AuthCard, authButtonCls, authInputCls, authLabelCls } from "@/components/site/AuthCard";

type LinkStatus = { purpose: "INVITE" | "RESET"; account_type: "CUSTOMER" | "INVESTOR"; login_path: string; expires_at: string };
type State =
  | { kind: "checking" }
  | { kind: "invalid"; message: string }
  | { kind: "ready"; token: string; status: LinkStatus }
  | { kind: "done"; loginPath: string };

const POLICY = [
  { test: (p: string) => p.length >= 12, label: "At least 12 characters" },
  { test: (p: string) => /[A-Z]/.test(p) && /[a-z]/.test(p), label: "Upper- and lower-case letters" },
  { test: (p: string) => /[0-9]/.test(p), label: "A number" },
  { test: (p: string) => /[^A-Za-z0-9]/.test(p), label: "A symbol" },
];
const INVALID = "This link is invalid or has expired. Please request a new one.";

/**
 * Invitation and password-reset landing page. The token arrives in the URL fragment (#token=…),
 * which browsers never send to any server, and is removed from the address bar immediately.
 */
export default function ResetPasswordPage() {
  const passwordId = useId();
  const confirmId = useId();
  const [state, setState] = useState<State>({ kind: "checking" });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Read once and kept in a ref: the fragment is cleared right away, and React may run effects twice.
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    if (tokenRef.current === null) {
      // Normally captured from the fragment by the layout's early script (see layout.tsx); the
      // fragment is the fallback. Either way it is removed from memory, URL and history here.
      const w = window as Window & { __ebLinkToken?: string };
      tokenRef.current = w.__ebLinkToken ?? new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
      delete w.__ebLinkToken;
      if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    }
    const token = tokenRef.current;
    const check: Promise<State> = token
      ? api<LinkStatus>("/auth/password/status", { method: "POST", body: { token } }).then(
          (status): State => ({ kind: "ready", token, status }),
          (err): State => ({ kind: "invalid", message: err instanceof ApiError && err.status === 429 ? err.detail : INVALID })
        )
      : Promise.resolve<State>({ kind: "invalid", message: INVALID });
    let active = true;
    void check.then((next) => active && setState(next));
    return () => {
      active = false;
    };
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy || state.kind !== "ready") return;
    setError(null);
    if (!POLICY.every((r) => r.test(password))) {
      setError("Choose a password that meets every requirement below.");
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<{ login_path: string }>("/auth/password/reset", { method: "POST", body: { token: state.token, new_password: password } });
      setPassword("");
      setConfirm("");
      setState({ kind: "done", loginPath: res.login_path });
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setState({ kind: "invalid", message: err.detail });
      else setError(err instanceof ApiError ? err.detail : "Unable to save the password. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const invite = state.kind === "ready" && state.status.purpose === "INVITE";
  const title = state.kind === "done" ? "Password saved" : invite ? "Set your password" : "Choose a new password";

  return (
    <AuthCard
      eyebrow={invite ? "Account invitation" : "Account recovery"}
      title={title}
      intro={
        state.kind === "ready"
          ? `${invite ? "Welcome. Choose the password for your" : "Choose a new password for your"} ${state.status.account_type === "INVESTOR" ? "investor" : "customer"} account. This link works once.`
          : undefined
      }
    >
      {state.kind === "checking" && (
        <p className="mt-8 flex items-center gap-2 text-sm text-ink-muted" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Checking your link…
        </p>
      )}

      {state.kind === "invalid" && (
        <>
          <AuthAlert tone="error">{state.message}</AuthAlert>
          <div className="mt-6 flex flex-wrap gap-4 text-sm">
            <Link href="/forgot-password" className="underline decoration-brand underline-offset-4 hover:text-brand">Request a new reset link</Link>
            <Link href="/login" className="underline decoration-line-strong underline-offset-4 hover:text-brand">Sign in</Link>
          </div>
        </>
      )}

      {state.kind === "done" && (
        <>
          <AuthAlert tone="ok">Your password has been saved and any other signed-in sessions were signed out. You can now sign in.</AuthAlert>
          <Link href={state.loginPath} className={`${authButtonCls} mt-6`}>
            Go to sign in <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </>
      )}

      {state.kind === "ready" && (
        <>
          {error && <AuthAlert tone="error">{error}</AuthAlert>}
          <form onSubmit={submit} noValidate aria-label={invite ? "Account invitation form" : "Password reset form"} className="mt-8 space-y-5">
            <div>
              <label htmlFor={passwordId} className={authLabelCls}>New password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
                <input id={passwordId} name="new-password" type={show ? "text" : "password"} autoComplete="new-password" required disabled={busy} value={password} onChange={(e) => setPassword(e.target.value)} aria-describedby={`${passwordId}-rules`} className={`${authInputCls} pr-14`} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"} aria-pressed={show} className="absolute inset-y-0 right-0 flex w-12 cursor-pointer items-center justify-center text-ink-subtle hover:text-ink">
                  {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </button>
              </div>
              <ul id={`${passwordId}-rules`} className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
                {POLICY.map((r) => (
                  <li key={r.label} className={r.test(password) ? "text-emerald-700 dark:text-emerald-300" : "text-ink-subtle"}>
                    {r.test(password) ? "✓" : "•"} {r.label}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <label htmlFor={confirmId} className={authLabelCls}>Confirm password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
                <input id={confirmId} name="confirm-password" type={show ? "text" : "password"} autoComplete="new-password" required disabled={busy} value={confirm} onChange={(e) => setConfirm(e.target.value)} className={authInputCls} />
              </div>
            </div>
            <button type="submit" disabled={busy} aria-busy={busy} className={authButtonCls}>
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Saving…
                </>
              ) : (
                <>
                  Save password <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" aria-hidden="true" />
                </>
              )}
            </button>
          </form>
        </>
      )}
    </AuthCard>
  );
}
