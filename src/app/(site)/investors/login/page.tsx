"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { BrandMark, Shell } from "@/components/site/primitives";

const inputCls =
  "eb-glass-inset block min-h-[3.25rem] w-full pl-11 text-[0.95rem] text-ink placeholder:text-ink-subtle/80 transition-[border-color,box-shadow] duration-300 focus-visible:border-brand focus-visible:shadow-[0_0_0_4px_var(--eb-glow)] focus-visible:outline-none disabled:opacity-50";

export default function InvestorLoginPage() {
  const router = useRouter();
  const emailId = useId();
  const passwordId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already signed in as an investor: go straight to the dashboard.
  useEffect(() => {
    let active = true;
    api("/investor/me")
      .then(() => active && router.replace("/investors/portal"))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [router]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    try {
      await api("/investor/login", { method: "POST", body: { email: email.trim(), password } });
      router.replace("/investors/portal");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("Invalid email or password.");
      else if (err instanceof ApiError && err.status === 403) setError(err.detail || "Please verify your email address before signing in.");
      else if (err instanceof ApiError && err.status === 422) setError("Please enter a valid email address.");
      else setError(err instanceof ApiError ? err.detail : "Unable to sign in. Please try again.");
      setBusy(false);
    }
  };

  return (
    <section className="relative isolate flex min-h-[100dvh] items-center overflow-hidden pb-16 pt-28 sm:pt-32">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <div className="absolute left-[8%] top-[14%] h-[30vmax] w-[30vmax] rounded-full bg-[radial-gradient(circle,color-mix(in_oklab,var(--eb-brand)_36%,transparent),transparent_65%)] blur-2xl" />
        <div className="eb-grid absolute inset-0 opacity-25 [mask-image:radial-gradient(55%_55%_at_50%_45%,black,transparent)]" />
      </div>
      <Shell>
        <div className="eb-glass mx-auto grid w-full max-w-[1040px] overflow-hidden lg:grid-cols-2">
          <div className="flex flex-col justify-between gap-12 border-b border-line p-8 sm:p-10 lg:border-b-0 lg:border-r lg:p-12">
            <div className="flex items-center gap-3 text-ink">
              <BrandMark className="h-10 w-10" />
              <span className="flex flex-col leading-none">
                <span className="text-[0.85rem] font-semibold tracking-[0.32em]">EDEN BOUNTY</span>
                <span className="mt-1.5 font-mono text-[0.58rem] tracking-[0.24em] text-ink-subtle">Investor relations</span>
              </span>
            </div>
            <div className="my-auto py-8">
              <p className="eb-eyebrow">Investors · Investor Login</p>
              <h1 className="eb-display mt-5 text-[clamp(2.4rem,4.6vw,3.8rem)] text-ink">
                Your investment <em className="text-brand">records</em>, in one place.
              </h1>
              <p className="mt-5 max-w-sm text-sm leading-relaxed text-ink-muted">
                Review your recorded investments, the services they relate to, and the documents and updates the company has issued to you.
              </p>
            </div>
            <p className="font-mono text-[0.6rem] uppercase leading-relaxed tracking-[0.18em] text-ink-subtle">
              EDEN BOUNTY Sdn. Bhd. · SSM 202501058702 (1660108-D)
            </p>
          </div>

          <div className="p-8 sm:p-10 lg:p-12">
            <h2 className="eb-display text-[2.4rem] text-ink">Investor login</h2>
            <p className="mt-2 text-sm text-ink-muted">Sign in to access your investment records, capital updates, and document library.</p>

            {error && (
              <div role="alert" className="mt-6 flex items-start gap-2.5 border border-[#FCA5A5] bg-[#FEF2F2]/90 p-3.5 text-sm text-[#B91C1C] dark:border-[#7F1D1D] dark:bg-[#1A0A0C]/80 dark:text-[#F87171]">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={submit} noValidate aria-label="Investor sign in" className="mt-8 space-y-5">
              <div>
                <label htmlFor={emailId} className="mb-2 block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted">Email</label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
                  <input id={emailId} name="email" type="email" autoComplete="email" required disabled={busy} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" className={`${inputCls} pr-4`} />
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-baseline justify-between gap-3">
                  <label htmlFor={passwordId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted">Password</label>
                  <Link href="/forgot-password?from=investor" className="text-xs text-ink-subtle underline decoration-line-strong underline-offset-4 hover:text-brand">Forgot password?</Link>
                </div>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
                  <input id={passwordId} name="password" type={show ? "text" : "password"} autoComplete="current-password" required disabled={busy} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" className={`${inputCls} pr-14`} />
                  <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"} aria-pressed={show} className="absolute inset-y-0 right-0 flex w-12 cursor-pointer items-center justify-center text-ink-subtle hover:text-ink">
                    {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                  </button>
                </div>
              </div>
              <button type="submit" disabled={busy} aria-busy={busy} className="group mt-3 flex min-h-[3.25rem] w-full cursor-pointer items-center justify-center gap-3 bg-brand px-5 text-[0.8rem] font-semibold uppercase tracking-[0.18em] text-brand-ink transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60">
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Verifying…
                  </>
                ) : (
                  <>
                    Sign in <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" aria-hidden="true" />
                  </>
                )}
              </button>
            </form>

            {/* Investor Public Registration Option */}
            <div className="mt-5 p-3.5 bg-panel-2 rounded-[2px] border border-line flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs">
              <div>
                <span className="block font-semibold text-ink">New investor?</span>
                <span className="text-[11px] text-ink-muted">Public registration is open to verified individuals and institutions.</span>
              </div>
              <Link
                href="/register?role=investor"
                className="shrink-0 font-mono text-[11px] uppercase tracking-wider text-brand font-semibold hover:underline"
              >
                Register Account →
              </Link>
            </div>

            <div className="mt-3 flex items-center justify-between gap-3 p-3 bg-panel rounded-[2px] border border-line text-xs">
              <span className="text-ink-muted">Customer or administrator?</span>
              <Link
                href="/login"
                className="font-mono uppercase tracking-wider text-ink-subtle hover:text-brand font-semibold"
              >
                Account & Admin Sign In →
              </Link>
            </div>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-line pt-6 text-xs text-ink-subtle">
              <Link href="/investors" className="inline-flex min-h-11 items-center gap-2 font-mono uppercase tracking-[0.18em] hover:text-brand">
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Investor overview
              </Link>
              <Link href="/register?role=investor" className="min-h-11 content-center font-semibold text-brand underline decoration-brand underline-offset-4 hover:text-brand-hover">
                Create an Investor Account →
              </Link>
            </div>
          </div>
        </div>
      </Shell>
    </section>
  );
}
