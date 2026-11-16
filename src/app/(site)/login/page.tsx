"use client";

import React, { useState, useEffect, useId, FormEvent, Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ArrowLeft,
  ArrowRight,
  WifiOff,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import { BrandMark, EASE } from "@/components/site/primitives";
import { SeaContours } from "@/components/site/SeaContours";
import { cn } from "@/lib/utils";
import { siteConfig } from "@/config/site";
import { AdminApiError } from "@/lib/admin-api";
import { api } from "@/lib/api";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { useToast } from "@/hooks/useToast";
import { sanitizeAdminReturnUrl } from "@/hooks/useSessionExpiry";
import { FormFieldError, FormErrorSummary, getInputValidationClasses } from "@/components/ui/states";
import { sanitizeErrorMessage } from "@/components/ui/states/StateError";

const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

function AdminLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading, login } = useAdminAuth();
  const { isOnline } = useNetworkStatus();
  const { toast } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | undefined>>({});

  const emailId = useId();
  const passwordId = useId();
  const errorId = useId();

  const safeReturnUrl = sanitizeAdminReturnUrl(searchParams?.get("returnUrl"));

  // Redirect to target or dashboard if session is already active
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(safeReturnUrl);
    }
  }, [isLoading, isAuthenticated, router, safeReturnUrl]);

  // A customer who is already signed in goes straight to the customer dashboard.
  useEffect(() => {
    if (isLoading || isAuthenticated) return;
    let active = true;
    api("/customer/me")
      .then(() => active && router.replace("/account"))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [isLoading, isAuthenticated, router]);

  const handleFocusField = useCallback((fieldName: string) => {
    const el = document.getElementById(fieldName === "email" ? emailId : passwordId);
    if (el) {
      el.focus();
    }
  }, [emailId, passwordId]);

  const validate = (): boolean => {
    const errors: Record<string, string | undefined> = {};
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      errors.email = "Email is required.";
    } else if (!EMAIL_REGEX.test(trimmedEmail)) {
      errors.email = "Please enter a valid email address.";
    }

    if (!password) {
      errors.password = "Password is required.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!isOnline) {
      toast.warning("A network connection is required to sign in.");
      return;
    }

    setErrorMessage(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const result = await login({ email: email.trim(), password });
      if (result.accountType === "CUSTOMER") {
        toast.success("Signed in. Welcome to your account.");
        router.replace(result.redirectTo || "/account");
      } else if (result.accountType === "INVESTOR") {
        toast.success("Signed in. Welcome to your investor dashboard.");
        router.replace(result.redirectTo || "/investors/portal");
      } else {
        toast.success("Signed in. Welcome back to the operations console.");
        router.replace(safeReturnUrl || "/admin");
      }
    } catch (err: unknown) {
      if (err instanceof AdminApiError) {
        if (err.status === 401) {
          setErrorMessage("Invalid credentials. Please verify your email and password.");
        } else if (err.status === 429) {
          setErrorMessage("Too many failed sign-in attempts. Please wait 15 minutes before trying again.");
        } else if (err.status === 403) {
          setErrorMessage(err.detail ? sanitizeErrorMessage(err.detail) : "Sign-in was refused by the server’s security policy. If this continues, contact the system administrator.");
        } else {
          setErrorMessage(sanitizeErrorMessage(err.detail));
        }
      } else {
        setErrorMessage("Unable to connect to the authentication service. Please check your network connection.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputBase =
    "eb-glass-inset peer block min-h-[3.25rem] w-full pl-11 text-[0.95rem] text-ink placeholder:text-ink-subtle/80 transition-[border-color,box-shadow,background-color] duration-300 focus-visible:outline-none focus-visible:border-brand focus-visible:shadow-[0_0_0_4px_var(--eb-glow)] disabled:opacity-50";

  return (
    <div>
      <div className="mb-8">
        <h2 className="eb-display text-[2.4rem] text-ink sm:text-[2.8rem]">Welcome back.</h2>
        <p className="mt-2 text-sm text-ink-muted">For EDEN BOUNTY administrators, customers, and investors. You are automatically routed to your own dashboard after signing in.</p>
      </div>

      {!isOnline && (
        <div
          role="status"
          aria-live="polite"
          className="mb-6 flex items-center gap-2.5 border border-[#FDE68A] bg-[#FFFBEB]/90 p-3 text-xs text-[#92400E] dark:border-[#B45309]/50 dark:bg-[#1C150A]/80 dark:text-[#FCD34D]"
        >
          <WifiOff className="h-4 w-4 shrink-0 text-[#D97706]" aria-hidden="true" />
          <span>
            <strong>Offline:</strong> an internet connection is required to establish a secure session.
          </span>
        </div>
      )}

      <FormErrorSummary errors={fieldErrors} title="Please correct the highlighted fields" onFieldClick={handleFocusField} />

      {errorMessage && (
        <motion.div
          id={errorId}
          role="alert"
          aria-live="assertive"
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex items-start gap-2.5 border border-[#FCA5A5] bg-[#FEF2F2]/90 p-3.5 text-sm text-[#B91C1C] backdrop-blur dark:border-[#7F1D1D] dark:bg-[#1A0A0C]/80 dark:text-[#F87171]"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="flex-1">{errorMessage}</span>
        </motion.div>
      )}

      <form onSubmit={handleSubmit} noValidate aria-label="Sign in" className="space-y-5">
        <div>
          <label htmlFor={emailId} className="mb-2 block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted">
            Email
          </label>
          <div className="group relative">
            <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle transition-colors group-focus-within:text-brand" aria-hidden="true" />
            <input
              id={emailId}
              name="email"
              type="email"
              autoComplete="email"
              required
              disabled={isSubmitting || !isOnline}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) {
                  setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }
              }}
              placeholder="name@company.com"
              aria-invalid={!!fieldErrors.email}
              aria-describedby={fieldErrors.email ? `${emailId}-error` : undefined}
              className={cn(inputBase, "pr-4", fieldErrors.email && getInputValidationClasses(true))}
            />
          </div>
          <FormFieldError id={`${emailId}-error`} error={fieldErrors.email} />
        </div>

        <div>
          <div className="mb-2 flex items-baseline justify-between gap-3">
            <label htmlFor={passwordId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted">
              Password
            </label>
            <Link href="/forgot-password" className="text-xs text-ink-subtle underline decoration-line-strong underline-offset-4 transition-colors hover:text-brand hover:decoration-brand">
              Forgot password?
            </Link>
          </div>
          <div className="group relative">
            <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle transition-colors group-focus-within:text-brand" aria-hidden="true" />
            <input
              id={passwordId}
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              disabled={isSubmitting || !isOnline}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (fieldErrors.password) {
                  setFieldErrors((prev) => ({ ...prev, password: undefined }));
                }
              }}
              placeholder="Enter your password"
              aria-invalid={!!fieldErrors.password}
              aria-describedby={fieldErrors.password ? `${passwordId}-error` : undefined}
              className={cn(inputBase, "pr-14", fieldErrors.password && getInputValidationClasses(true))}
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              className="absolute inset-y-0 right-0 flex w-12 cursor-pointer items-center justify-center text-ink-subtle transition-colors hover:text-ink focus-visible:text-brand"
            >
              {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
            </button>
          </div>
          <FormFieldError id={`${passwordId}-error`} error={fieldErrors.password} />
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !isOnline}
          aria-busy={isSubmitting}
          className="group relative mt-3 flex min-h-[3.25rem] w-full cursor-pointer items-center justify-center gap-3 overflow-hidden bg-brand px-5 text-[0.8rem] font-semibold uppercase tracking-[0.18em] text-brand-ink shadow-[0_14px_40px_-14px_var(--eb-glow)] transition-[background-color,box-shadow,transform] duration-300 hover:bg-brand-hover hover:shadow-[0_18px_50px_-12px_var(--eb-glow)] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span
            className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-white/25 opacity-0 transition-[transform,opacity] duration-700 group-hover:translate-x-[420%] group-hover:opacity-100 motion-reduce:hidden"
            aria-hidden="true"
          />
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              <span>Verifying…</span>
            </>
          ) : (
            <>
              <span>Sign in</span>
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" aria-hidden="true" />
            </>
          )}
        </button>
      </form>

      {/* Registration Options */}
      <div className="mt-5 p-3.5 bg-panel-2 rounded-[2px] border border-line space-y-2 text-xs">
        <div className="flex items-center justify-between gap-3">
          <span className="text-ink-muted">New customer?</span>
          <Link
            href="/register?role=customer"
            className="font-mono text-[11px] uppercase tracking-wider text-brand font-semibold hover:underline"
          >
            Register Customer Account →
          </Link>
        </div>
        <div className="flex items-center justify-between gap-3 pt-2 border-t border-line/60">
          <span className="text-ink-muted">New investor?</span>
          <Link
            href="/register?role=investor"
            className="font-mono text-[11px] uppercase tracking-wider text-brand font-semibold hover:underline"
          >
            Register Investor Account →
          </Link>
        </div>
      </div>

      {/* Investor Dedicated Option */}
      <div className="mt-3 flex items-center justify-between gap-3 p-3 bg-panel rounded-[2px] border border-line text-xs">
        <span className="text-ink-muted">Existing investor?</span>
        <Link
          href="/investors/login"
          className="font-mono uppercase tracking-wider text-ink-subtle hover:text-brand font-semibold"
        >
          Dedicated Investor Login →
        </Link>
      </div>

      <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-line pt-6 text-xs text-ink-subtle">
        <Link href="/" className="inline-flex min-h-11 items-center gap-2 font-mono uppercase tracking-[0.18em] transition-colors hover:text-brand">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Back to website
        </Link>
        <Link href="/register?role=customer" className="min-h-11 content-center font-semibold text-brand underline decoration-brand underline-offset-4 transition-colors hover:text-brand-hover">
          Need an account? Register here →
        </Link>
      </div>
    </div>
  );
}

export default function LoginPage() {
  const reduce = useReducedMotion();

  return (
    <section className="relative isolate flex min-h-[100dvh] items-center overflow-hidden px-4 pb-16 pt-28 sm:px-8 sm:pt-32">
      {/* Ambient lighting */}
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <motion.div
          className="absolute left-[4%] top-[10%] h-[34vmax] w-[34vmax] rounded-full bg-[radial-gradient(circle,color-mix(in_oklab,var(--eb-brand)_42%,transparent),transparent_65%)] blur-2xl"
          animate={reduce ? undefined : { x: [0, 30, 0], y: [0, -20, 0] }}
          transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute bottom-[-6%] right-[6%] h-[38vmax] w-[38vmax] rounded-full bg-[radial-gradient(circle,rgba(56,200,190,0.34),transparent_65%)] blur-2xl"
          animate={reduce ? undefined : { x: [0, -24, 0], y: [0, 18, 0] }}
          transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="absolute left-[46%] top-[34%] h-[18vmax] w-[18vmax] rounded-full bg-[radial-gradient(circle,rgba(80,150,230,0.3),transparent_65%)] blur-xl" />
        <div className="eb-grid absolute inset-0 opacity-25 [mask-image:radial-gradient(55%_55%_at_50%_45%,black,transparent)]" />
      </div>
      <SeaContours lines={5} top={58} step={8} />
      <div className="eb-grain" aria-hidden="true" />

      <motion.div
        className="eb-glass relative mx-auto grid w-full max-w-[1080px] overflow-hidden lg:grid-cols-[1.05fr_1fr]"
        initial={{ opacity: 0, y: reduce ? 0 : 28, scale: reduce ? 1 : 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.9, ease: EASE }}
      >
        {/* Brand panel */}
        <div className="relative flex flex-col justify-between gap-12 overflow-hidden border-b border-line p-8 sm:p-10 lg:border-b-0 lg:border-r lg:p-12">
          <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(80%_60%_at_0%_0%,var(--eb-glow),transparent_70%)] opacity-70" aria-hidden="true" />
          <div className="flex items-center gap-3 text-ink">
            <BrandMark className="h-10 w-10" />
            <span className="flex flex-col leading-none">
              <span className="text-[0.85rem] font-semibold tracking-[0.32em]">EDEN BOUNTY</span>
              <span className="mt-1.5 font-mono text-[0.58rem] tracking-[0.24em] text-ink-subtle">Sdn. Bhd. · Malaysia</span>
            </span>
          </div>

          <div className="my-auto py-8">
            <p className="eb-eyebrow">Account sign-in</p>
            <h1 className="eb-display mt-5 text-[clamp(2.6rem,5vw,4.2rem)] text-ink">
              One sign-in, the <em className="text-brand">right</em> dashboard.
            </h1>
            <p className="mt-5 max-w-sm text-sm leading-relaxed text-ink-muted sm:text-base">
              Administrators manage enquiries, customers and orders. Customers follow their own enquiries, orders and shipments.
            </p>
          </div>

          <p className="font-mono text-[0.6rem] uppercase leading-relaxed tracking-[0.18em] text-ink-subtle">
            {siteConfig.legalName} · SSM {siteConfig.contact.registrationNumber}
          </p>
        </div>

        {/* Form panel */}
        <div className="relative p-8 sm:p-10 lg:p-12">
          <Suspense
            fallback={
              <div className="flex min-h-[420px] items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-brand" aria-label="Loading sign-in form" />
              </div>
            }
          >
            <AdminLoginForm />
          </Suspense>
        </div>
      </motion.div>
    </section>
  );
}
