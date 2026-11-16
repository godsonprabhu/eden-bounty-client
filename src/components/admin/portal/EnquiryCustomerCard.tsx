"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useToast } from "@/hooks/useToast";
import { OrdersTable } from "@/components/portal/OrderViews";
import { Button, ConfirmDialog, Dialog, errorText, Field, FormError, Panel, Resource, useResource } from "@/components/portal/ui";
import type { OrderSummary, PortalUser, PortalUserAdmin } from "@/types/portal";
import { OrderCreateDialog } from "./OrderCreateDialog";
import { useAdminApi } from "./useAdminApi";

interface Link_ {
  customer: PortalUser | null;
  orders: OrderSummary[];
}

/**
 * Customer link, customer-visible updates and order conversion for one enquiry.
 * Linking is always an explicit administrator decision; nothing is matched by email automatically.
 */
export function EnquiryCustomerCard({ enquiry, onChanged }: { enquiry: { id: string; reference_number: string; product_focus: string; business_email: string }; onChanged?: () => void }) {
  const { send } = useAdminApi();
  const { toast } = useToast();
  const link = useResource<Link_>(`/admin/rfqs/${enquiry.id}/customer`);
  const [linkOpen, setLinkOpen] = useState(false);
  const customers = useResource<PortalUserAdmin[]>(linkOpen ? "/admin/portal-users?role=CUSTOMER" : null);
  const [selected, setSelected] = useState("");
  const [unlinkOpen, setUnlinkOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [orderOpen, setOrderOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>, success: string, after: () => void) => {
    setError(null);
    setBusy(true);
    try {
      await action();
      toast.success(success);
      after();
      link.reload();
      onChanged?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Customer & order" description="Link this enquiry to a customer account, post updates the customer can read, and convert it into an order.">
      <Resource state={link} rows={2}>
        {(data) => (
          <div className="space-y-5">
            {data.customer ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border border-line bg-panel-2 p-4">
                <div className="min-w-0">
                  <p className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-subtle">Linked customer</p>
                  <Link href={`/admin/customers/${data.customer.id}`} className="text-sm font-semibold text-ink underline decoration-brand underline-offset-4 hover:text-brand">{data.customer.full_name}</Link>
                  <p className="text-xs text-ink-muted [overflow-wrap:anywhere]">{data.customer.email}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" className="min-h-9" onClick={() => { setError(null); setMessage(""); }}>Post customer update</Button>
                  <Button variant="danger" className="min-h-9" onClick={() => { setError(null); setUnlinkOpen(true); }}>Unlink</Button>
                </div>
              </div>
            ) : (
              <div className="border border-line bg-panel-2 p-4">
                <p className="text-sm text-ink-muted">
                  Not linked to a customer account, so no customer can see it. Link it only after confirming who submitted it — the enquiry was sent from <span className="font-semibold text-ink [overflow-wrap:anywhere]">{enquiry.business_email}</span>.
                </p>
                <Button variant="ghost" className="mt-3 min-h-9" onClick={() => { setError(null); setSelected(""); setLinkOpen(true); }}>Link to customer</Button>
              </div>
            )}

            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-ink-subtle">Orders from this enquiry</p>
                <Button className="min-h-9" onClick={() => setOrderOpen(true)}>Convert to order</Button>
              </div>
              {data.orders.length === 0 ? <p className="text-sm text-ink-muted">No order has been created from this enquiry.</p> : <OrdersTable orders={data.orders} hrefBase="/admin/orders" />}
            </div>

            <Dialog open={linkOpen} title="Link enquiry to a customer" onClose={() => setLinkOpen(false)} busy={busy}>
              <form
                className="space-y-4"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  if (!selected) return setError("Select a customer.");
                  void run(() => send(`/admin/rfqs/${enquiry.id}/customer`, "POST", { customer_id: selected }), "Enquiry linked. It is now visible in the customer's dashboard.", () => setLinkOpen(false));
                }}
              >
                <p className="text-sm text-ink-muted">By linking, you confirm this customer submitted enquiry {enquiry.reference_number}. They will see its details, status and any customer-visible updates. Internal notes stay hidden.</p>
                <Field
                  label="Customer"
                  as="select"
                  required
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  options={[{ value: "", label: customers.loading ? "Loading customers…" : "Select a customer" }, ...(customers.data ?? []).map((c) => ({ value: c.id, label: `${c.full_name} (${c.email})${c.email === enquiry.business_email.toLowerCase() ? " — same email as enquiry" : ""}` }))]}
                />
                <FormError message={error || customers.error} />
                <div className="flex justify-end gap-2">
                  <Button variant="ghost" onClick={() => setLinkOpen(false)} disabled={busy}>Cancel</Button>
                  <Button type="submit" busy={busy}>Confirm and link</Button>
                </div>
              </form>
            </Dialog>

            <Dialog open={message !== null} title="Post an update to the customer" onClose={() => setMessage(null)} busy={busy}>
              <form
                className="space-y-4"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  void run(() => send(`/admin/rfqs/${enquiry.id}/customer-updates`, "POST", { message: message ?? "" }), "Update posted to the customer.", () => setMessage(null));
                }}
              >
                <Field label="Message" as="textarea" required maxLength={2000} value={message ?? ""} onChange={(e) => setMessage(e.target.value)} hint="The customer will read this exactly as written. Use internal notes for anything confidential." />
                <FormError message={error} />
                <div className="flex justify-end gap-2">
                  <Button variant="ghost" onClick={() => setMessage(null)} disabled={busy}>Cancel</Button>
                  <Button type="submit" busy={busy}>Post update</Button>
                </div>
              </form>
            </Dialog>

            <ConfirmDialog
              open={unlinkOpen}
              title="Unlink this enquiry?"
              message={<>The customer will no longer see this enquiry in their dashboard. The enquiry and any orders already created are kept.{error && <span className="mt-3 block text-red-600">{error}</span>}</>}
              confirmLabel="Unlink"
              danger
              busy={busy}
              onClose={() => setUnlinkOpen(false)}
              onConfirm={() => void run(() => send(`/admin/rfqs/${enquiry.id}/customer`, "POST", { customer_id: null }), "Enquiry unlinked.", () => setUnlinkOpen(false))}
            />

            <OrderCreateDialog open={orderOpen} onClose={() => setOrderOpen(false)} customerId={data.customer?.id} enquiry={{ id: enquiry.id, reference_number: enquiry.reference_number, product: enquiry.product_focus }} />
          </div>
        )}
      </Resource>
    </Panel>
  );
}
