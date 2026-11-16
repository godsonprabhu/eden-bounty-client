"use client";

import React, { useState, useEffect, useRef, FormEvent, Suspense } from "react";
import Link from "next/link";
import { CheckCircle2, AlertCircle, Loader2, ArrowRight, Mail } from "lucide-react";
import { BrandMark } from "@/components/site/primitives";
import { SeaContours } from "@/components/site/SeaContours";
import { api, ApiError } from "@/lib/api";

type VerificationState =
  | { kind: "verifying" }
  | { kind: "success"; message: string; redirectTo: string }
  | { kind: "error"; message: string }
  | { kind: "no-token" };

function VerifyEmailContent() {
  const [state, setState] = useState<VerificationState>({ kind: "verifying" });
  const tokenRef = useRef<string | null>(null);
  const promiseRef = useRef<Promise<VerificationState> | null>(null);

  // Resend form state
  const [resendEmail, setResendEmail] = useState("");
  const [isResending, setIsResending] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  useEffect(() => {
    if (tokenRef.current === null) {
      let rawToken: string | null = null;
      const hash = window.location.hash;
      if (hash && hash.includes("token=")) {
        const hashMatch = hash.match(/token=([^&]+)/);
        if (hashMatch && hashMatch[1]) {
          rawToken = decodeURIComponent(hashMatch[1]);
        }
      }
      if (!rawToken) {
        const searchParams = new URLSearchParams(window.location.search);
        rawToken = searchParams.get("token");
      }
      tokenRef.current = rawToken ?? "";
    }

    const token = tokenRef.current;
    if (!promiseRef.current) {
      promiseRef.current = token
        ? api<{ message: string; redirect_to?: string }>("/auth/verify-email", {
            method: "POST",
            body: { token },
          }).then(
            (res): VerificationState => ({
              kind: "success",
              message: res?.message || "Email address verified successfully.",
              redirectTo: res?.redirect_to || "/login",
            }),
            (err: unknown): VerificationState => ({
              kind: "error",
              message:
                err instanceof ApiError
                  ? err.detail
                  : err instanceof Error
                  ? err.message
                  : "Invalid or expired verification link.",
            })
          )
        : Promise.resolve<VerificationState>({ kind: "no-token" });
    }

    let active = true;
    void promiseRef.current.then((next) => {
      if (active) setState(next);
    });

    return () => {
      active = false;
    };
  }, []);

  const handleResend = async (e: FormEvent) => {
    e.preventDefault();
    if (!resendEmail.trim()) return;

    setIsResending(true);
    setResendMessage(null);
    try {
      const res = await api<{
        message: string;
      }>("/auth/resend-verification", {
        method: "POST",
        body: {
          email: resendEmail.trim().toLowerCase(),
        },
      });
      setResendMessage(res?.message || "If an unverified account exists, a verification link has been dispatched.");
    } catch {
      setResendMessage("If an unverified account exists, a verification link has been dispatched.");
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="eb-glass eb-glass-hover relative overflow-hidden rounded-[2px] border border-line p-7 sm:p-10 shadow-2xl">
      <div className="mb-6 flex items-center justify-between border-b border-line pb-4">
        <div>
          <span className="font-mono text-[0.66rem] uppercase tracking-[0.24em] text-brand">
            Account Security
          </span>
          <h2 className="eb-display text-2xl font-bold text-ink mt-1">
            Email Verification
          </h2>
        </div>
        <BrandMark className="h-6 w-auto text-ink opacity-60" />
      </div>

      {state.kind === "verifying" && (
        <div className="py-12 text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-brand mx-auto" />
          <p className="text-sm text-ink-muted">Verifying your single-use security token…</p>
        </div>
      )}

      {state.kind === "success" && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="rounded-[2px] border border-emerald-500/40 bg-emerald-500/10 p-5 text-sm text-ink space-y-3">
            <div className="flex items-center gap-2.5 text-emerald-600 dark:text-emerald-400 font-bold">
              <CheckCircle2 className="h-5 w-5 shrink-0" />
              <span>Email Verified Successfully</span>
            </div>
            <p className="text-xs leading-relaxed text-ink-muted">
              {state.message}
            </p>
          </div>

          <div className="pt-2">
            <Link
              href={state.redirectTo}
              className="group flex min-h-[48px] w-full items-center justify-center gap-2 rounded-[2px] bg-brand px-5 text-xs font-heading font-semibold uppercase tracking-wider text-brand-ink transition-colors hover:bg-brand-hover shadow-sm"
            >
              <span>Proceed to Portal Sign In</span>
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>
      )}

      {state.kind === "error" && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="rounded-[2px] border border-rose-500/40 bg-rose-500/10 p-5 text-sm text-ink space-y-2">
            <div className="flex items-center gap-2.5 text-rose-600 dark:text-rose-400 font-bold">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <span>Verification Failed</span>
            </div>
            <p className="text-xs leading-relaxed text-ink-muted">
              {state.message}
            </p>
          </div>

          {/* Resend Form */}
          <form onSubmit={handleResend} className="space-y-4 pt-2">
            <p className="text-xs text-ink-subtle">
              If your link has expired, enter your registered email address to receive a fresh verification link:
            </p>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                type="email"
                required
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full rounded-[2px] border border-line-strong bg-panel-2 py-2.5 pl-11 pr-4 text-xs text-ink placeholder:text-ink-subtle/70 focus:border-brand focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={isResending}
              className="w-full min-h-[44px] flex items-center justify-center gap-2 rounded-[2px] border border-line-strong bg-panel hover:bg-panel-2 text-xs font-semibold uppercase tracking-wider text-ink transition-colors cursor-pointer"
            >
              {isResending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Sending…</span>
                </>
              ) : (
                <span>Request Fresh Verification Link</span>
              )}
            </button>
          </form>

          {resendMessage && (
            <p className="text-xs text-brand bg-brand-soft p-3 rounded-[2px] border border-brand/30">
              {resendMessage}
            </p>
          )}

          <div className="pt-4 border-t border-line flex items-center justify-between text-xs text-ink-subtle">
            <Link href="/register" className="hover:text-brand font-mono uppercase tracking-wider">
              ← Back to Registration
            </Link>
            <Link href="/login" className="text-brand underline decoration-brand underline-offset-4">
              Return to Login
            </Link>
          </div>
        </div>
      )}

      {state.kind === "no-token" && (
        <div className="space-y-6 text-center py-6">
          <p className="text-sm text-ink-muted leading-relaxed">
            No verification token was detected in the URL. Please ensure you clicked the complete link sent to your registered email address.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 text-xs pt-4 border-t border-line">
            <Link href="/register" className="font-mono uppercase tracking-wider text-brand font-semibold hover:underline">
              Register New Account
            </Link>
            <span className="text-line">•</span>
            <Link href="/login" className="hover:text-brand">
              Sign In
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <section className="relative isolate flex min-h-[100dvh] items-center justify-center overflow-hidden px-4 pb-16 pt-28 sm:px-8 sm:pt-32">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <SeaContours />
      </div>

      <div className="w-full max-w-lg">
        <Suspense
          fallback={
            <div className="eb-glass flex min-h-[300px] items-center justify-center rounded-[2px] border border-line p-8">
              <Loader2 className="h-6 w-6 animate-spin text-brand" />
            </div>
          }
        >
          <VerifyEmailContent />
        </Suspense>
      </div>
    </section>
  );
}
