"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button, Dialog, errorText, FormError, fmtDateTime } from "@/components/portal/ui";
import type { PasswordLink } from "@/types/portal";

/**
 * Shows the result of issuing an invitation or password-reset link.
 *
 * With email delivery the server reports the real outcome: SENT once the mail server accepted the
 * message, FAILED otherwise (that link is already revoked, so "Try again" issues a fresh one).
 * Without email (MANUAL) the link is shown here exactly once: the server keeps only its hash, so
 * closing this dialog discards it. Administrators never see or choose the account's password.
 */
export function PasswordLinkDialog({
  result,
  email,
  onClose,
  onRetry,
}: {
  result: PasswordLink | null;
  email: string;
  onClose: () => void;
  /** Issues a new link (POST /admin/portal-users/{id}/password-link) and returns its result. */
  onRetry?: () => Promise<PasswordLink>;
}) {
  const [copied, setCopied] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retried, setRetried] = useState<PasswordLink | null>(null);
  if (!result) return null;
  const shown = retried ?? result;
  const kind = shown.purpose === "INVITE" ? "invitation" : "password reset";
  const close = () => {
    setCopied(false);
    setRetried(null);
    setRetryError(null);
    onClose();
  };
  const retry = async () => {
    if (!onRetry) return;
    setRetrying(true);
    setRetryError(null);
    try {
      setRetried(await onRetry());
    } catch (err) {
      setRetryError(errorText(err));
    } finally {
      setRetrying(false);
    }
  };
  const copy = async () => {
    if (!shown.link) return;
    try {
      await navigator.clipboard.writeText(shown.link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Dialog open title={shown.purpose === "INVITE" ? "Invitation link" : "Password reset link"} onClose={close} busy={retrying}>
      {shown.delivery === "EMAIL" && shown.delivery_status === "SENT" ? (
        <p role="status" className="text-sm leading-relaxed text-ink-muted">
          The mail server accepted the single-use {kind} email to <strong className="text-ink">{email}</strong>. The link expires {fmtDateTime(shown.expires_at)}. Any earlier link for this account no longer works. If it does not arrive (check the spam folder), issue a new link.
        </p>
      ) : shown.delivery === "EMAIL" ? (
        <div className="space-y-4 text-sm leading-relaxed text-ink-muted">
          <p role="alert" className="border border-red-600/40 bg-red-500/10 px-3 py-2 text-red-700 dark:text-red-300">
            The {kind} email to <strong>{email}</strong> could not be sent. That link has been cancelled, so nothing usable was delivered.
          </p>
          <p>Try again now, or later from the account page. If it keeps failing, the mail service may be unavailable; contact the system administrator.</p>
          <FormError message={retryError} />
        </div>
      ) : (
        <div className="space-y-4 text-sm leading-relaxed text-ink-muted">
          <p>
            Email delivery is not configured, so pass this single-use {kind} link to <strong className="text-ink">{email}</strong> yourself, over a channel you trust (for example a phone call or your usual secure messaging). Do not post it in shared channels.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              readOnly
              aria-label={`${kind} link`}
              value={shown.link ?? ""}
              onFocus={(e) => e.currentTarget.select()}
              className="min-h-10 w-full min-w-0 border border-line-strong bg-panel-2 px-3 py-2 font-mono text-xs text-ink"
            />
            <Button variant="ghost" onClick={copy} className="shrink-0">
              {copied ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <ul className="list-disc space-y-1 pl-5 text-xs">
            <li>It expires {fmtDateTime(shown.expires_at)} and works once. Any earlier link for this account no longer works.</li>
            <li>This is the only time the link is shown. If it is lost, issue a new one.</li>
            <li>The account holder chooses their own password; it is never visible to administrators.</li>
          </ul>
        </div>
      )}
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        {shown.delivery === "EMAIL" && shown.delivery_status === "FAILED" && onRetry && (
          <Button variant="ghost" onClick={retry} busy={retrying}>Try again</Button>
        )}
        <Button onClick={close} disabled={retrying}>Done</Button>
      </div>
    </Dialog>
  );
}
