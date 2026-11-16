"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { useToast } from "@/hooks/useToast";
import { Button, Dialog, Empty, errorText, Field, type FieldChange, FormError, fmtDate, fmtDateTime, PageHeader, Panel, Resource, StatusBadge, Table, td, tdStrong, useResource } from "@/components/portal/ui";
import { StatePermissionDenied } from "@/components/ui/states";
import type { PasswordLink, PortalRole, PortalUserAdmin, PortalUserCreated } from "@/types/portal";
import { PasswordLinkDialog } from "./PasswordLinkDialog";
import { useAdminApi } from "./useAdminApi";

const COPY = {
  CUSTOMER: { plural: "Customers", singular: "customer", base: "/admin/customers", intro: "Customer accounts are created here. Customers sign in on the main login page and see only their own enquiries and orders." },
  INVESTOR: { plural: "Investors", singular: "investor", base: "/admin/investors", intro: "Investor accounts are created here. Investors sign in on the investor login page and see only their own records." },
} as const;

const EMPTY_FORM = { email: "", full_name: "", company_name: "", contact_number: "", country: "" };

export function accountStatus(u: PortalUserAdmin): string {
  if (!u.is_active) return "INACTIVE";
  if (u.locked_until && new Date(u.locked_until) > new Date()) return "LOCKED";
  if (u.invitation_pending) return "INVITED";
  return "ACTIVE";
}

export function AccountsList({ role }: { role: PortalRole }) {
  const copy = COPY[role];
  const { send, isSuperAdmin } = useAdminApi();
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const allowed = role === "CUSTOMER" || isSuperAdmin;
  const users = useResource<PortalUserAdmin[]>(allowed ? `/admin/portal-users?role=${role}${query ? `&search=${encodeURIComponent(query)}` : ""}` : null);

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<{ link: PasswordLink; email: string; id: string } | null>(null);

  if (!allowed) return <StatePermissionDenied />;

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await send<PortalUserCreated>("/admin/portal-users", "POST", { role, ...form });
      toast.success(`${copy.singular[0].toUpperCase()}${copy.singular.slice(1)} account created.`);
      setOpen(false);
      setForm(EMPTY_FORM);
      setIssued({ link: created.invitation, email: created.email, id: created.id });
      users.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };
  const set = (k: keyof typeof EMPTY_FORM) => (e: FieldChange) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`${copy.plural} management`}
        title={copy.plural}
        intro={copy.intro}
        actions={<Button onClick={() => setOpen(true)}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> New {copy.singular}</Button>}
      />
      <Panel>
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(search.trim());
          }}
          className="mb-5 flex flex-wrap items-end gap-2"
        >
          <Field label={`Search ${copy.plural.toLowerCase()}`} placeholder="Name, email or company" value={search} onChange={(e) => setSearch(e.target.value)} className="min-w-0 flex-1 basis-56" />
          <Button type="submit" variant="ghost"><Search className="h-3.5 w-3.5" aria-hidden="true" /> Search</Button>
        </form>
        <Resource state={users} isEmpty={(d) => d.length === 0} empty={<Empty title={query ? "No accounts match your search" : `No ${copy.singular} accounts yet`}>{!query && `Create the first ${copy.singular} account with the button above.`}</Empty>}>
          {(rows) => (
            <Table caption={copy.plural} head={["Name", "Email", "Company", "Created", "Last sign-in", "Status"]}>
              {rows.map((u) => (
                <tr key={u.id}>
                  <td className={tdStrong}>
                    <Link href={`${copy.base}/${u.id}`} className="underline decoration-brand underline-offset-4 hover:text-brand">{u.full_name}</Link>
                  </td>
                  <td className={td + " [overflow-wrap:anywhere]"}>{u.email}</td>
                  <td className={td}>{u.company_name || "—"}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtDate(u.created_at)}</td>
                  <td className={td + " whitespace-nowrap"}>{fmtDateTime(u.last_login_at)}</td>
                  <td className={td}><StatusBadge status={accountStatus(u)} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Resource>
      </Panel>

      <Dialog open={open} title={`New ${copy.singular} account`} onClose={() => setOpen(false)} busy={busy}>
        <form onSubmit={create} className="space-y-4">
          <Field label="Full name" required maxLength={150} value={form.full_name} onChange={set("full_name")} />
          <Field label="Sign-in email" type="email" required value={form.email} onChange={set("email")} hint="Must not already be used by any administrator, customer or investor." />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Company" maxLength={200} value={form.company_name} onChange={set("company_name")} />
            <Field label="Country" maxLength={100} value={form.country} onChange={set("country")} />
          </div>
          <Field label="Contact number" maxLength={50} value={form.contact_number} onChange={set("contact_number")} />
          <p className="text-xs leading-relaxed text-ink-muted">
            No password is set here. Creating the account issues a single-use invitation link (valid for 72 hours) with which the {copy.singular} chooses their own password.
          </p>
          <FormError message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
            <Button type="submit" busy={busy}>Create account</Button>
          </div>
        </form>
      </Dialog>

      <PasswordLinkDialog
        result={issued?.link ?? null}
        email={issued?.email ?? ""}
        onClose={() => setIssued(null)}
        onRetry={issued ? () => send<PasswordLink>(`/admin/portal-users/${issued.id}/password-link`, "POST") : undefined}
      />
    </div>
  );
}
