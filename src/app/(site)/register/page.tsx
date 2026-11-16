"use client";

import React, { useState, useId, FormEvent, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Lock,
  Mail,
  User,
  Building,
  Phone,
  Globe,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ArrowRight,
  Check,
} from "lucide-react";
import { BrandMark } from "@/components/site/primitives";
import { SeaContours } from "@/components/site/SeaContours";
import { siteConfig } from "@/config/site";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { FormFieldError, getInputValidationClasses } from "@/components/ui/states";

const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

function RegisterForm() {
  const searchParams = useSearchParams();

  const initialRoleParam = searchParams?.get("role")?.toUpperCase();
  const [role, setRole] = useState<"CUSTOMER" | "INVESTOR">(
    initialRoleParam === "INVESTOR" ? "INVESTOR" : "CUSTOMER"
  );

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [contactNumber, setContactNumber] = useState("");
  const [country, setCountry] = useState("Malaysia");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | undefined>>({});
  const [registrationSuccess, setRegistrationSuccess] = useState<{
    delivery: string;
    message: string;
    email: string;
  } | null>(null);

  const nameId = useId();
  const emailId = useId();
  const companyId = useId();
  const phoneId = useId();
  const countryId = useId();
  const passwordId = useId();
  const confirmPasswordId = useId();
  const termsId = useId();

  // Password requirements calculation
  const passChecks = {
    length: password.length >= 12,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    digit: /[0-9]/.test(password),
    special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?`~]/.test(password),
  };
  const isPasswordStrong = Object.values(passChecks).every(Boolean);

  const validate = (): boolean => {
    const errs: Record<string, string | undefined> = {};

    if (!fullName.trim()) {
      errs.fullName = "Full name is required.";
    }

    if (!email.trim()) {
      errs.email = "Email address is required.";
    } else if (!EMAIL_REGEX.test(email.trim())) {
      errs.email = "Please enter a valid email address.";
    }

    if (!password) {
      errs.password = "Password is required.";
    } else if (!isPasswordStrong) {
      errs.password = "Password does not satisfy all security requirements.";
    }

    if (password !== confirmPassword) {
      errs.confirmPassword = "Passwords do not match.";
    }

    if (!termsAccepted) {
      errs.terms = "You must accept the terms of trade and confidentiality declaration.";
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const response = await api<{
        user: unknown;
        delivery: string;
        verification_link?: string | null;
        message: string;
      }>("/auth/register", {
        method: "POST",
        body: {
          role,
          full_name: fullName.trim(),
          email: email.trim().toLowerCase(),
          company_name: companyName.trim() || undefined,
          contact_number: contactNumber.trim() || undefined,
          country: country.trim() || undefined,
          password,
        },
      });

      if (response) {
        setRegistrationSuccess({
          delivery: response.delivery,
          message: response.message,
          email: email.trim().toLowerCase(),
        });
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Registration failed. Please check your details.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputBase =
    "w-full rounded-[2px] border border-line-strong bg-panel-2 py-2.5 pl-11 pr-4 text-sm text-ink placeholder:text-ink-subtle/70 transition-colors focus:border-brand focus:bg-panel focus:outline-none focus:ring-1 focus:ring-brand disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="eb-glass eb-glass-hover relative overflow-hidden rounded-[2px] border border-line p-7 sm:p-10 shadow-2xl">
      <div className="mb-6 flex items-center justify-between border-b border-line pb-4">
        <div>
          <span className="font-mono text-[0.66rem] uppercase tracking-[0.24em] text-brand">
            Account Creation
          </span>
          <h2 className="eb-display text-2xl font-bold text-ink mt-1">
            Register for Portal Access
          </h2>
        </div>
        <BrandMark className="h-6 w-auto text-ink opacity-60" />
      </div>

      {registrationSuccess ? (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="rounded-[2px] border border-[#10B981]/40 bg-[#10B981]/10 p-5 text-sm text-ink space-y-3">
            <div className="flex items-center gap-2.5 text-[#059669] dark:text-[#10B981] font-bold">
              <CheckCircle2 className="h-5 w-5 shrink-0" />
              <span>Registration Successful</span>
            </div>
            <p className="text-xs leading-relaxed text-ink-muted">
              {registrationSuccess.message}
            </p>
            <p className="font-mono text-xs text-brand font-semibold break-all">
              Registered address: {registrationSuccess.email}
            </p>
          </div>

          <div className="pt-4 border-t border-line flex flex-wrap items-center justify-between gap-3 text-xs">
            <Link
              href={role === "INVESTOR" ? "/investors/login" : "/login"}
              className="font-mono uppercase tracking-wider text-brand font-semibold hover:underline inline-flex items-center gap-1.5"
            >
              <span>Proceed to Portal Sign In</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <button
              type="button"
              onClick={() => {
                setRegistrationSuccess(null);
                setPassword("");
                setConfirmPassword("");
              }}
              className="text-ink-subtle hover:text-ink underline underline-offset-4"
            >
              Register another account
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          {/* Role Selector Tabs */}
          <div>
            <label className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-2">
              Select Account Type
            </label>
            <div className="grid grid-cols-2 gap-2 p-1 bg-panel-2 rounded-[2px] border border-line">
              <button
                type="button"
                onClick={() => setRole("CUSTOMER")}
                className={`py-2 px-3 text-xs font-heading font-semibold rounded-[2px] transition-all cursor-pointer ${
                  role === "CUSTOMER"
                    ? "bg-brand text-brand-ink shadow-sm"
                    : "text-ink-muted hover:text-ink hover:bg-panel"
                }`}
              >
                Customer Portal
              </button>
              <button
                type="button"
                onClick={() => setRole("INVESTOR")}
                className={`py-2 px-3 text-xs font-heading font-semibold rounded-[2px] transition-all cursor-pointer ${
                  role === "INVESTOR"
                    ? "bg-brand text-brand-ink shadow-sm"
                    : "text-ink-muted hover:text-ink hover:bg-panel"
                }`}
              >
                Investor Portal
              </button>
            </div>
            <p className="mt-1.5 text-[11px] text-ink-subtle">
              {role === "CUSTOMER"
                ? "For commercial trade enquiries, RFQ submissions, and purchase orders."
                : "For verified stakeholders and corporate investment documents."}
            </p>
          </div>

          {/* Enterprise SSO / OAuth Notice */}
          <div className="p-3 bg-panel-2 rounded-[2px] border border-line text-xs">
            <span className="block font-semibold text-ink">Enterprise Single Sign-On</span>
            <span className="text-[11px] text-ink-muted">
              Google Workspace SSO is in configuration. Register below with your corporate email to create your verified account.
            </span>
          </div>

          <div className="relative flex items-center justify-center my-4">
            <div className="border-t border-line w-full" />
            <span className="bg-paper-2 px-3 text-[10px] font-mono uppercase tracking-widest text-ink-subtle shrink-0">
              Or Register with Email
            </span>
          </div>

          {errorMessage && (
            <div
              role="alert"
              className="rounded-[2px] border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-600 dark:text-rose-400 font-mono flex items-center gap-2"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Full Name */}
          <div>
            <label htmlFor={nameId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
              Full Name *
            </label>
            <div className="relative">
              <User className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                id={nameId}
                name="fullName"
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g., Captain Azman bin Rahim"
                className={cn(inputBase, fieldErrors.fullName && getInputValidationClasses(true))}
              />
            </div>
            <FormFieldError error={fieldErrors.fullName} />
          </div>

          {/* Business Email */}
          <div>
            <label htmlFor={emailId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
              Business Email Address *
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                id={emailId}
                name="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className={cn(inputBase, fieldErrors.email && getInputValidationClasses(true))}
              />
            </div>
            <FormFieldError error={fieldErrors.email} />
          </div>

          {/* Company Name */}
          <div>
            <label htmlFor={companyId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
              Company / Entity Name {role === "CUSTOMER" ? "*" : "(Optional)"}
            </label>
            <div className="relative">
              <Building className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                id={companyId}
                name="companyName"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Registered enterprise name"
                className={inputBase}
              />
            </div>
          </div>

          {/* Contact Number & Country */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor={phoneId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
                Phone Number (Optional)
              </label>
              <div className="relative">
                <Phone className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
                <input
                  id={phoneId}
                  name="contactNumber"
                  type="tel"
                  value={contactNumber}
                  onChange={(e) => setContactNumber(e.target.value)}
                  placeholder="+60 12-345 6789"
                  className={inputBase}
                />
              </div>
            </div>

            <div>
              <label htmlFor={countryId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
                Country of Operation
              </label>
              <div className="relative">
                <Globe className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
                <input
                  id={countryId}
                  name="country"
                  type="text"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  placeholder="e.g. Malaysia"
                  className={inputBase}
                />
              </div>
            </div>
          </div>

          {/* Password & Confirm */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor={passwordId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
                Password * (min 12 chars)
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
                <input
                  id={passwordId}
                  name="password"
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create secure password"
                  className={cn(inputBase, "pr-11", fieldErrors.password && getInputValidationClasses(true))}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-subtle hover:text-ink cursor-pointer"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <FormFieldError error={fieldErrors.password} />
            </div>

            <div>
              <label htmlFor={confirmPasswordId} className="block font-mono text-[0.66rem] uppercase tracking-[0.2em] text-ink-muted mb-1.5">
                Confirm Password *
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
                <input
                  id={confirmPasswordId}
                  name="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat password"
                  className={cn(inputBase, "pr-11", fieldErrors.confirmPassword && getInputValidationClasses(true))}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-subtle hover:text-ink cursor-pointer"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <FormFieldError error={fieldErrors.confirmPassword} />
            </div>
          </div>

          {/* Password Policy Guidance */}
          <div className="rounded-[2px] border border-line bg-panel p-3 text-[11px] space-y-1.5">
            <span className="font-mono text-[10px] uppercase text-ink-subtle block font-semibold">
              Security Standards (Argon2id Salted Hash):
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 text-ink-muted">
              <span className={`flex items-center gap-1 ${passChecks.length ? "text-emerald-600 font-semibold" : ""}`}>
                {passChecks.length ? <Check className="h-3 w-3" /> : "•"} 12+ Characters
              </span>
              <span className={`flex items-center gap-1 ${passChecks.upper ? "text-emerald-600 font-semibold" : ""}`}>
                {passChecks.upper ? <Check className="h-3 w-3" /> : "•"} Uppercase (A-Z)
              </span>
              <span className={`flex items-center gap-1 ${passChecks.lower ? "text-emerald-600 font-semibold" : ""}`}>
                {passChecks.lower ? <Check className="h-3 w-3" /> : "•"} Lowercase (a-z)
              </span>
              <span className={`flex items-center gap-1 ${passChecks.digit ? "text-emerald-600 font-semibold" : ""}`}>
                {passChecks.digit ? <Check className="h-3 w-3" /> : "•"} Digit (0-9)
              </span>
              <span className={`flex items-center gap-1 ${passChecks.special ? "text-emerald-600 font-semibold" : ""}`}>
                {passChecks.special ? <Check className="h-3 w-3" /> : "•"} Symbol (!@#$…)
              </span>
            </div>
          </div>

          {/* Terms & Privacy Declaration */}
          <div className="space-y-1.5">
            <label htmlFor={termsId} className="flex items-start gap-3 cursor-pointer text-xs text-ink-muted">
              <input
                id={termsId}
                name="termsAccepted"
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded-[2px] border-line-strong text-brand focus:ring-brand cursor-pointer"
              />
              <span>
                I agree to the corporate terms of use, privacy governance, and commercial confidentiality declarations of {siteConfig.legalName}.
              </span>
            </label>
            <FormFieldError error={fieldErrors.terms} />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="group relative flex min-h-[3.25rem] w-full cursor-pointer items-center justify-center gap-3 overflow-hidden bg-brand px-5 text-[0.82rem] font-semibold uppercase tracking-[0.18em] text-brand-ink shadow-md transition-all duration-300 hover:bg-brand-hover active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Registering Account…</span>
              </>
            ) : (
              <>
                <span>Create {role === "INVESTOR" ? "Investor" : "Customer"} Account</span>
                <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
              </>
            )}
          </button>

          <div className="pt-4 border-t border-line flex flex-wrap items-center justify-between gap-3 text-xs text-ink-subtle">
            <Link href="/" className="hover:text-brand font-mono uppercase tracking-wider">
              ← Return to site
            </Link>
            <Link
              href={role === "INVESTOR" ? "/investors/login" : "/login"}
              className="text-brand font-semibold underline underline-offset-4 hover:text-brand-hover"
            >
              Already registered? Sign in here →
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

export default function RegisterPage() {
  return (
    <section className="relative isolate flex min-h-[100dvh] items-center justify-center overflow-hidden px-4 pb-16 pt-28 sm:px-8 sm:pt-32">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <SeaContours />
      </div>

      <div className="w-full max-w-xl">
        <Suspense
          fallback={
            <div className="eb-glass flex min-h-[400px] items-center justify-center rounded-[2px] border border-line p-8">
              <Loader2 className="h-6 w-6 animate-spin text-brand" />
            </div>
          }
        >
          <RegisterForm />
        </Suspense>
      </div>
    </section>
  );
}
