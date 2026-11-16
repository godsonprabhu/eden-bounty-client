"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Plus, Upload } from "lucide-react";
import { businessDivisions } from "@/data/divisions";
import { apiUrl } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { InvestmentsTable } from "@/components/portal/InvestmentsTable";
import { OrdersTable } from "@/components/portal/OrderViews";
import { Button, ConfirmDialog, DefinitionList, Dialog, Empty, errorText, Field, FormError, fmtBytes, fmtDate, fmtDateTime, humanize, PageHeader, Panel, Resource, StatusBadge, Table, td, tdStrong, useResource } from "@/components/portal/ui";
import { StatePermissionDenied } from "@/components/ui/states";
import { DOCUMENT_CATEGORIES, INVESTMENT_STATUSES, type Investment, type InvestorUpdate, type PasswordLink, type PortalRole, type PortalUserAdminDetail } from "@/types/portal";
import { accountStatus } from "./AccountsList";
import { PasswordLinkDialog } from "./PasswordLinkDialog";
import { OrderCreateDialog } from "./OrderCreateDialog";
import { useAdminApi } from "./useAdminApi";

const BASE = { CUSTOMER: "/admin/customers", INVESTOR: "/admin/investors" } as const;
const today = () => new Date().toISOString().slice(0, 10);

export function AccountDetail({ role, id }: { role: PortalRole; id: string }) {
  const { send, isSuperAdmin } = useAdminApi();
  const { toast } = useToast();
  const allowed = role === "CUSTOMER" || isSuperAdmin;
  const account = useResource<PortalUserAdminDetail>(allowed ? `/admin/portal-users/${encodeURIComponent(id)}` : null);

  const [edit, setEdit] = useState<null | { full_name: string; company_name: string; contact_number: string; country: string }>(null);
  const [confirmToggle, setConfirmToggle] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [issued, setIssued] = useState<PasswordLink | null>(null);
  const [orderOpen, setOrderOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!allowed) return <StatePermissionDenied />;

  const run = async (action: () => Promise<unknown>, success: string, after?: () => void) => {
    setError(null);
    setBusy(true);
    try {
      await action();
      toast.success(success);
      after?.();
      account.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Link href={BASE[role]} className="inline-flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.16em] text-ink-muted hover:text-brand">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> All {role === "CUSTOMER" ? "customers" : "investors"}
      </Link>
      <Resource state={account}>
        {(u) =>
          u.role !== role ? (
            <Empty title="Account not found" />
          ) : (
            <>
              <PageHeader
                eyebrow={role === "CUSTOMER" ? "Customer" : "Investor"}
                title={u.full_name}
                intro={u.email}
                actions={
                  <>
                    <StatusBadge status={accountStatus(u)} />
                    <Button variant="ghost" onClick={() => { setError(null); setEdit({ full_name: u.full_name, company_name: u.company_name ?? "", contact_number: u.contact_number ?? "", country: u.country ?? "" }); }}>Edit</Button>
                    <Button variant="ghost" onClick={() => { setError(null); setLinkOpen(true); }} disabled={!u.is_active}>{u.invitation_pending ? "Resend invitation" : "Send password reset link"}</Button>
                    <Button variant={u.is_active ? "danger" : "primary"} onClick={() => { setError(null); setConfirmToggle(true); }}>{u.is_active ? "Deactivate" : "Activate"}</Button>
                  </>
                }
              />
              <Panel title="Account information">
                <DefinitionList
                  items={[
                    ["Company", u.company_name],
                    ["Contact number", u.contact_number],
                    ["Country", u.country],
                    ["Created", fmtDateTime(u.created_at)],
                    ["Last sign-in", fmtDateTime(u.last_login_at)],
                    ["Password", u.invitation_pending ? "Not set yet (invitation pending)" : "Set by the account holder"],
                    ["Open link", u.active_link ? `${u.active_link.purpose === "INVITE" ? "Invitation" : "Password reset"}, expires ${fmtDateTime(u.active_link.expires_at)}` : "None"],
                    ...(u.last_link_email ? ([["Last link email", u.last_link_email.status === "SENT" ? `Sent ${fmtDateTime(u.last_link_email.at)}` : `Failed ${fmtDateTime(u.last_link_email.at)}; that link was cancelled. Send a new one.`]] as Array<[string, React.ReactNode]>) : []),
                    ...(u.reset_requested_at ? ([["Reset requested", `${fmtDateTime(u.reset_requested_at)} (verify the requester, then send a reset link)`]] as Array<[string, React.ReactNode]>) : []),
                  ]}
                />
              </Panel>

              {role === "CUSTOMER" ? (
                <>
                  <Panel title="Orders" actions={<Button onClick={() => setOrderOpen(true)} disabled={!u.is_active}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> New order</Button>}>
                    {u.orders.length === 0 ? <Empty title="No orders for this customer yet" /> : <OrdersTable orders={u.orders} hrefBase="/admin/orders" />}
                  </Panel>
                  <Panel title="Linked enquiries" description="Enquiries are linked from the enquiry record, after confirming the customer submitted them.">
                    {u.enquiries.length === 0 ? (
                      <Empty title="No enquiries linked">Open an enquiry and use &ldquo;Customer &amp; order&rdquo; to link it to this account.</Empty>
                    ) : (
                      <Table caption="Linked enquiries" head={["Reference", "Company on enquiry", "Product", "Submitted", "Status"]}>
                        {u.enquiries.map((e) => (
                          <tr key={e.id}>
                            <td className={tdStrong}><Link href={`/admin/enquiries/${e.id}`} className="font-mono text-xs underline decoration-brand underline-offset-4 hover:text-brand">{e.reference_number}</Link></td>
                            <td className={td}>{e.company_name}</td>
                            <td className={td}>{e.product_focus}</td>
                            <td className={td + " whitespace-nowrap"}>{fmtDate(e.created_at)}</td>
                            <td className={td}><StatusBadge status={e.status} /></td>
                          </tr>
                        ))}
                      </Table>
                    )}
                  </Panel>
                  <OrderCreateDialog open={orderOpen} onClose={() => setOrderOpen(false)} customerId={u.id} />
                </>
              ) : (
                <InvestorSections investor={u} onChanged={account.reload} />
              )}

              <Dialog open={!!edit} title="Edit account details" onClose={() => setEdit(null)} busy={busy}>
                {edit && (
                  <form
                    className="space-y-4"
                    onSubmit={(e: FormEvent) => {
                      e.preventDefault();
                      void run(() => send(`/admin/portal-users/${u.id}`, "PATCH", edit), "Account details updated.", () => setEdit(null));
                    }}
                  >
                    <Field label="Full name" required maxLength={150} value={edit.full_name} onChange={(e) => setEdit({ ...edit, full_name: e.target.value })} />
                    <Field label="Company" maxLength={200} value={edit.company_name} onChange={(e) => setEdit({ ...edit, company_name: e.target.value })} />
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Contact number" maxLength={50} value={edit.contact_number} onChange={(e) => setEdit({ ...edit, contact_number: e.target.value })} />
                      <Field label="Country" maxLength={100} value={edit.country} onChange={(e) => setEdit({ ...edit, country: e.target.value })} />
                    </div>
                    <FormError message={error} />
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" onClick={() => setEdit(null)} disabled={busy}>Cancel</Button>
                      <Button type="submit" busy={busy}>Save</Button>
                    </div>
                  </form>
                )}
              </Dialog>

              <ConfirmDialog
                open={linkOpen}
                title={u.invitation_pending ? "Resend invitation?" : "Send a password reset link?"}
                message={
                  <>
                    {u.invitation_pending
                      ? `Issues a new single-use invitation link for ${u.full_name} (valid for 72 hours). Any earlier link stops working.`
                      : `Issues a single-use reset link for ${u.full_name} (valid for 30 minutes). Their current password keeps working until they use it; using it signs them out everywhere. Any earlier link stops working.`}
                    {error && <span className="mt-3 block text-red-600">{error}</span>}
                  </>
                }
                confirmLabel={u.invitation_pending ? "Issue invitation" : "Issue reset link"}
                busy={busy}
                onClose={() => setLinkOpen(false)}
                onConfirm={() =>
                  void run(
                    async () => setIssued(await send<PasswordLink>(`/admin/portal-users/${u.id}/password-link`, "POST")),
                    u.invitation_pending ? "Invitation issued." : "Reset link issued.",
                    () => setLinkOpen(false)
                  )
                }
              />
              <PasswordLinkDialog
                result={issued}
                email={u.email}
                onClose={() => { setIssued(null); account.reload(); }}
                onRetry={() => send<PasswordLink>(`/admin/portal-users/${u.id}/password-link`, "POST")}
              />

              <ConfirmDialog
                open={confirmToggle}
                title={u.is_active ? "Deactivate this account?" : "Activate this account?"}
                message={
                  <>
                    {u.is_active
                      ? `${u.full_name} will be signed out immediately and will not be able to sign in. Their records are kept and nothing is deleted.`
                      : u.invitation_pending
                        ? `${u.full_name} has not set a password yet. After activating, resend the invitation.`
                        : `${u.full_name} will be able to sign in again with their existing password.`}
                    {error && <span className="mt-3 block text-red-600">{error}</span>}
                  </>
                }
                confirmLabel={u.is_active ? "Deactivate" : "Activate"}
                danger={u.is_active}
                busy={busy}
                onClose={() => setConfirmToggle(false)}
                onConfirm={() => void run(() => send(`/admin/portal-users/${u.id}`, "PATCH", { is_active: !u.is_active }), u.is_active ? "Account deactivated." : "Account activated.", () => setConfirmToggle(false))}
              />
            </>
          )
        }
      </Resource>
    </div>
  );
}

/* ------------------------------------------------------------------ investor-only sections */
function InvestorSections({ investor, onChanged }: { investor: PortalUserAdminDetail; onChanged: () => void }) {
  const { send } = useAdminApi();
  const { toast } = useToast();
  const updates = useResource<InvestorUpdate[]>(`/admin/investor-updates?investor_id=${investor.id}`);
  const fileRef = useRef<HTMLInputElement>(null);

  const blankInvestment = { id: "", division_id: "", amount: "", currency: "MYR", invested_on: today(), status: "ACTIVE", summary: "" };
  const [investment, setInvestment] = useState<null | typeof blankInvestment>(null);
  const [doc, setDoc] = useState<null | { title: string; category: string }>(null);
  const [update, setUpdate] = useState<null | { title: string; body: string; is_published: boolean }>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>, success: string, after: () => void) => {
    setError(null);
    setBusy(true);
    try {
      await action();
      toast.success(success);
      after();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const saveInvestment = (e: FormEvent) => {
    e.preventDefault();
    if (!investment) return;
    const { id, ...fields } = investment;
    const body = { ...fields, summary: fields.summary.trim() };
    void run(
      () => (id ? send(`/admin/investments/${id}`, "PATCH", body) : send("/admin/investments", "POST", { investor_id: investor.id, ...body })),
      id ? "Investment record updated." : "Investment record added.",
      () => { setInvestment(null); onChanged(); }
    );
  };

  const uploadDocument = (e: FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!doc || !file) {
      setError("Choose a PDF file to upload.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError("The file is larger than 15 MB.");
      return;
    }
    const qs = new URLSearchParams({ title: doc.title.trim(), filename: file.name, category: doc.category });
    void run(
      () => send(`/admin/investors/${investor.id}/documents?${qs}`, "POST", undefined, { raw: file, contentType: "application/pdf" }),
      "Document uploaded. It stays hidden from the investor until you publish it.",
      () => { setDoc(null); onChanged(); }
    );
  };

  const editInvestment = (i: Investment) => {
    setError(null);
    setInvestment({ id: i.id, division_id: i.division.id, amount: i.amount, currency: i.currency, invested_on: i.invested_on, status: i.status, summary: i.summary ?? "" });
  };

  return (
    <>
      <Panel title="Investment records" description="Amounts recorded for this investor, assigned to a business division." actions={<Button onClick={() => { setError(null); setInvestment(blankInvestment); }}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add investment</Button>}>
        {investor.investments.length === 0 ? (
          <Empty title="No investment records yet" />
        ) : (
          <InvestmentsTable investments={investor.investments} action={(i) => <Button variant="ghost" className="min-h-8 px-3" onClick={() => editInvestment(i)}>Edit</Button>} />
        )}
      </Panel>

      <Panel title="Private documents" description="PDF only, up to 15 MB. Stored privately; investors download through their signed-in session." actions={<Button onClick={() => { setError(null); setDoc({ title: "", category: "FINANCIAL_REPORT" }); }}><Upload className="h-3.5 w-3.5" aria-hidden="true" /> Upload document</Button>}>
        {investor.documents.length === 0 ? (
          <Empty title="No documents uploaded" />
        ) : (
          <Table caption="Investor documents" head={["Title", "Type", "Uploaded", "Size", "Visibility", ""]}>
            {investor.documents.map((d) => (
              <tr key={d.id}>
                <td className={tdStrong + " [overflow-wrap:anywhere]"}>{d.title}<span className="block text-xs font-normal text-ink-subtle">{d.original_filename}</span></td>
                <td className={td}>{humanize(d.category)}</td>
                <td className={td + " whitespace-nowrap"}>{fmtDate(d.created_at)}</td>
                <td className={td + " whitespace-nowrap"}>{fmtBytes(d.size_bytes)}</td>
                <td className={td}><StatusBadge status={d.is_published ? "PUBLISHED" : "DRAFT"} label={d.is_published ? "Published" : "Hidden"} /></td>
                <td className={td}>
                  <span className="flex flex-wrap justify-end gap-2">
                    <a href={apiUrl(`/admin/investor-documents/${d.id}/download`)} className="inline-flex min-h-8 items-center gap-1.5 border border-line-strong px-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink hover:border-brand hover:text-brand">
                      <Download className="h-3.5 w-3.5" aria-hidden="true" /><span className="sr-only">Download {d.title}</span>
                    </a>
                    <Button variant="ghost" className="min-h-8 px-3" disabled={busy} onClick={() => void run(() => send(`/admin/investor-documents/${d.id}`, "PATCH", { is_published: !d.is_published }), d.is_published ? "Document hidden from the investor." : "Document published to the investor.", onChanged)}>
                      {d.is_published ? "Unpublish" : "Publish"}
                    </Button>
                  </span>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>

      <Panel title="Investor updates" description="Updates addressed to this investor, plus announcements sent to all investors." actions={<Button onClick={() => { setError(null); setUpdate({ title: "", body: "", is_published: true }); }}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> New update</Button>}>
        <Resource state={updates} isEmpty={(d) => d.length === 0} empty={<Empty title="No updates yet" />}>
          {(rows) => (
            <ul className="divide-y divide-line">
              {rows.map((u) => (
                <li key={u.id} className="flex flex-wrap items-start justify-between gap-3 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink [overflow-wrap:anywhere]">{u.title}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-ink-muted [overflow-wrap:anywhere]">{u.body}</p>
                    <p className="mt-1 text-xs text-ink-subtle">{fmtDate(u.created_at)} · {u.investor_id ? "This investor only" : "All investors"}</p>
                  </div>
                  <span className="flex items-center gap-2">
                    <StatusBadge status={u.is_published ? "PUBLISHED" : "DRAFT"} />
                    <Button variant="ghost" className="min-h-8 px-3" disabled={busy} onClick={() => void run(() => send(`/admin/investor-updates/${u.id}`, "PATCH", { is_published: !u.is_published }), u.is_published ? "Update unpublished." : "Update published.", updates.reload)}>
                      {u.is_published ? "Unpublish" : "Publish"}
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Resource>
      </Panel>

      <Dialog open={!!investment} title={investment?.id ? "Edit investment record" : "Add investment record"} onClose={() => setInvestment(null)} busy={busy}>
        {investment && (
          <form onSubmit={saveInvestment} className="space-y-4">
            <Field label="Business division" as="select" required value={investment.division_id} onChange={(e) => setInvestment({ ...investment, division_id: e.target.value })} options={[{ value: "", label: "Select a division" }, ...businessDivisions.map((d) => ({ value: d.id, label: d.name }))]} />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Amount" type="number" required min="0.01" step="0.01" inputMode="decimal" value={investment.amount} onChange={(e) => setInvestment({ ...investment, amount: e.target.value })} className="sm:col-span-2" />
              <Field label="Currency" required maxLength={3} value={investment.currency} onChange={(e) => setInvestment({ ...investment, currency: e.target.value.toUpperCase() })} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Investment date" type="date" required value={investment.invested_on} onChange={(e) => setInvestment({ ...investment, invested_on: e.target.value })} />
              <Field label="Status" as="select" value={investment.status} onChange={(e) => setInvestment({ ...investment, status: e.target.value })} options={INVESTMENT_STATUSES.map((s) => ({ value: s, label: humanize(s) }))} />
            </div>
            <Field label="Summary for the investor" as="textarea" maxLength={2000} value={investment.summary} onChange={(e) => setInvestment({ ...investment, summary: e.target.value })} hint="Shown to the investor. Record facts only; do not state expected returns or projections." />
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setInvestment(null)} disabled={busy}>Cancel</Button>
              <Button type="submit" busy={busy}>{investment.id ? "Save changes" : "Add record"}</Button>
            </div>
          </form>
        )}
      </Dialog>

      <Dialog open={!!doc} title="Upload private document" onClose={() => setDoc(null)} busy={busy}>
        {doc && (
          <form onSubmit={uploadDocument} className="space-y-4">
            <Field label="Title" required maxLength={200} value={doc.title} onChange={(e) => setDoc({ ...doc, title: e.target.value })} />
            <Field label="Type" as="select" value={doc.category} onChange={(e) => setDoc({ ...doc, category: e.target.value })} options={DOCUMENT_CATEGORIES.map((c) => ({ value: c, label: humanize(c) }))} />
            <div>
              <label htmlFor="investor-document-file" className="mb-1.5 block font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-subtle">PDF file <span className="text-brand">*</span></label>
              <input ref={fileRef} id="investor-document-file" type="file" accept="application/pdf,.pdf" required className="block w-full text-sm text-ink-muted file:mr-3 file:cursor-pointer file:border file:border-line-strong file:bg-panel-2 file:px-3 file:py-2 file:text-xs file:font-semibold file:uppercase file:tracking-wider file:text-ink" />
            </div>
            <p className="text-xs text-ink-subtle">The document is uploaded as hidden. Publish it from the list when it has been approved for release to this investor.</p>
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDoc(null)} disabled={busy}>Cancel</Button>
              <Button type="submit" busy={busy}>Upload</Button>
            </div>
          </form>
        )}
      </Dialog>

      <Dialog open={!!update} title={`New update for ${investor.full_name}`} onClose={() => setUpdate(null)} busy={busy}>
        {update && (
          <form
            className="space-y-4"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void run(() => send("/admin/investor-updates", "POST", { ...update, investor_id: investor.id }), update.is_published ? "Update published to the investor." : "Update saved as a draft.", () => { setUpdate(null); updates.reload(); });
            }}
          >
            <Field label="Title" required maxLength={200} value={update.title} onChange={(e) => setUpdate({ ...update, title: e.target.value })} />
            <Field label="Message" as="textarea" required maxLength={10000} value={update.body} onChange={(e) => setUpdate({ ...update, body: e.target.value })} />
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={update.is_published} onChange={(e) => setUpdate({ ...update, is_published: e.target.checked })} className="h-4 w-4 accent-[var(--eb-brand)]" />
              Publish immediately
            </label>
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setUpdate(null)} disabled={busy}>Cancel</Button>
              <Button type="submit" busy={busy}>Save update</Button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}
