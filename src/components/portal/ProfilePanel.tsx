"use client";

import { useState, type FormEvent } from "react";
import { PORTAL_AREAS, usePortalAuth } from "@/context/PortalAuthContext";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Button, DefinitionList, errorText, Field, FormError, fmtDateTime, PageHeader, Panel } from "./ui";

/** Profile, contact details, password change and sign-out. Shared by the customer and investor portals. */
export function ProfilePanel() {
  const { area, user, csrfToken, refresh, logout } = usePortalAuth();
  const { toast } = useToast();
  const base = PORTAL_AREAS[area].api;

  const [contact, setContact] = useState({
    full_name: user?.full_name ?? "",
    company_name: user?.company_name ?? "",
    contact_number: user?.contact_number ?? "",
    country: user?.country ?? "",
  });
  const [savingContact, setSavingContact] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);

  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm: "" });
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  if (!user) return null;

  const saveContact = async (e: FormEvent) => {
    e.preventDefault();
    setContactError(null);
    setSavingContact(true);
    try {
      await api(`${base}/profile`, { method: "PATCH", body: contact, csrf: csrfToken });
      await refresh();
      toast.success("Your details were updated.");
    } catch (err) {
      setContactError(errorText(err));
    } finally {
      setSavingContact(false);
    }
  };

  const savePassword = async (e: FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    if (passwords.new_password !== passwords.confirm) {
      setPasswordError("The new password and its confirmation do not match.");
      return;
    }
    setSavingPassword(true);
    try {
      await api(`${base}/password`, {
        method: "POST",
        body: { current_password: passwords.current_password, new_password: passwords.new_password },
        csrf: csrfToken,
      });
      setPasswords({ current_password: "", new_password: "", confirm: "" });
      toast.success("Password changed. Other devices were signed out.");
    } catch (err) {
      setPasswordError(errorText(err));
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Profile" title="Your account" intro="Review your account information, keep your contact details current and manage your password." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Account information">
          <DefinitionList
            items={[
              ["Name", user.full_name],
              ["Sign-in email", user.email],
              ["Account type", area === "customer" ? "Customer" : "Investor"],
              ["Last sign-in", fmtDateTime(user.last_login_at)],
            ]}
          />
          <p className="mt-4 text-xs text-ink-subtle">Your sign-in email can only be changed by the company. Please write to us if it needs updating.</p>
        </Panel>

        <Panel title="Contact information">
          <form onSubmit={saveContact} className="space-y-4">
            <Field label="Full name" required maxLength={150} value={contact.full_name} onChange={(e) => setContact({ ...contact, full_name: e.target.value })} autoComplete="name" />
            <Field label="Company" maxLength={200} value={contact.company_name} onChange={(e) => setContact({ ...contact, company_name: e.target.value })} autoComplete="organization" />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Contact number" maxLength={50} value={contact.contact_number} onChange={(e) => setContact({ ...contact, contact_number: e.target.value })} autoComplete="tel" />
              <Field label="Country" maxLength={100} value={contact.country} onChange={(e) => setContact({ ...contact, country: e.target.value })} autoComplete="country-name" />
            </div>
            <FormError message={contactError} />
            <Button type="submit" busy={savingContact}>Save details</Button>
          </form>
        </Panel>

        <Panel title="Password" description="At least 12 characters with upper and lower case letters, a number and a symbol.">
          <form onSubmit={savePassword} className="space-y-4">
            <Field label="Current password" type="password" required value={passwords.current_password} onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })} autoComplete="current-password" />
            <Field label="New password" type="password" required minLength={12} value={passwords.new_password} onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} autoComplete="new-password" />
            <Field label="Confirm new password" type="password" required minLength={12} value={passwords.confirm} onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })} autoComplete="new-password" />
            <FormError message={passwordError} />
            <Button type="submit" busy={savingPassword}>Change password</Button>
          </form>
        </Panel>

        <Panel title="Sign out" description="Ends this session on this device.">
          <Button variant="ghost" onClick={logout}>Log out securely</Button>
        </Panel>
      </div>
    </>
  );
}
