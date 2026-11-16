"use client";

import { Suspense, useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Loader2, Mail } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { AuthAlert, AuthCard, authButtonCls, authInputCls, authLabelCls } from "@/components/site/AuthCard";

function ForgotPasswordForm() {
  const params = useSearchParams();
  const loginPath = params.get("from") === "investor" ? "/investors/login" : "/login";
  const emailId = useId();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError("Please enter a valid email address.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<{ message: string }>("/auth/password/forgot", { method: "POST", body: { email: email.trim() } });
      setDone(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to send the request. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard
      eyebrow="Account recovery"
      title="Forgot your password?"
      intro="Enter the email address of your customer or investor account. Administrators reset their access through the company's internal procedure."
    >
      {done ? (
        <AuthAlert tone="ok">{done}</AuthAlert>
      ) : (
        <>
          {error && <AuthAlert tone="error">{error}</AuthAlert>}
          <form onSubmit={submit} noValidate aria-label="Request a password reset" className="mt-8 space-y-5">
            <div>
              <label htmlFor={emailId} className={authLabelCls}>Email</label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
                <input id={emailId} name="email" type="email" autoComplete="email" required disabled={busy} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" className={authInputCls} />
              </div>
            </div>
            <button type="submit" disabled={busy} aria-busy={busy} className={authButtonCls}>
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Sending…
                </>
              ) : (
                <>
                  Request reset link <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" aria-hidden="true" />
                </>
              )}
            </button>
          </form>
        </>
      )}
      <div className="mt-8 border-t border-line pt-6 text-xs text-ink-subtle">
        <Link href={loginPath} className="inline-flex min-h-11 items-center gap-2 font-mono uppercase tracking-[0.18em] hover:text-brand">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Back to sign in
        </Link>
      </div>
    </AuthCard>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense>
      <ForgotPasswordForm />
    </Suspense>
  );
}
