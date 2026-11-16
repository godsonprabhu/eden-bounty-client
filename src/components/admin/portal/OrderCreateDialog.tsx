"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { businessDivisions } from "@/data/divisions";
import { useToast } from "@/hooks/useToast";
import { Button, Dialog, errorText, Field, type FieldChange, FormError, useResource } from "@/components/portal/ui";
import type { AdminOrderDetail, PortalUserAdmin } from "@/types/portal";
import { useAdminApi } from "./useAdminApi";

/**
 * Creates an order for a customer. With `enquiry`, the order is a conversion of that enquiry:
 * product, quantity and division default to the enquiry's values on the server.
 */
export function OrderCreateDialog({
  open,
  onClose,
  customerId,
  enquiry,
}: {
  open: boolean;
  onClose: () => void;
  /** Fixed customer (when opened from a customer record or a linked enquiry). */
  customerId?: string;
  enquiry?: { id: string; reference_number: string; product: string };
}) {
  const router = useRouter();
  const { send } = useAdminApi();
  const { toast } = useToast();
  const customers = useResource<PortalUserAdmin[]>(open && !customerId ? "/admin/portal-users?role=CUSTOMER" : null);
  const [form, setForm] = useState({ customer_id: "", division_id: "", product_description: "", quantity: "", unit_of_measurement: "", total_amount: "", currency: "MYR", customer_note: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: FieldChange) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const customer = customerId || form.customer_id;
    if (!customer) {
      setError("Select the customer this order belongs to.");
      return;
    }
    const body: Record<string, unknown> = { customer_id: customer };
    if (enquiry) body.enquiry_id = enquiry.id;
    if (form.division_id) body.division_id = form.division_id;
    if (form.product_description.trim()) body.product_description = form.product_description.trim();
    if (form.quantity) body.quantity = form.quantity;
    if (form.unit_of_measurement.trim()) body.unit_of_measurement = form.unit_of_measurement.trim();
    if (form.total_amount) {
      body.total_amount = form.total_amount;
      body.currency = form.currency;
    }
    if (form.customer_note.trim()) body.customer_note = form.customer_note.trim();
    setBusy(true);
    try {
      const order = await send<AdminOrderDetail>("/admin/orders", "POST", body);
      toast.success(`Order ${order.reference_number} created.`);
      onClose();
      router.push(`/admin/orders/${order.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  const optional = enquiry ? "Leave blank to use the enquiry's value." : undefined;

  return (
    <Dialog open={open} title={enquiry ? `Convert ${enquiry.reference_number} to an order` : "New order"} onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-4">
        {enquiry && <p className="border border-line bg-panel-2 p-3 text-sm text-ink-muted">The order will be created from this enquiry ({enquiry.product}) and will appear in the customer&rsquo;s dashboard immediately.</p>}
        {!customerId && (
          <Field
            label="Customer"
            as="select"
            required
            value={form.customer_id}
            onChange={set("customer_id")}
            options={[{ value: "", label: customers.loading ? "Loading customers…" : "Select a customer" }, ...(customers.data ?? []).filter((c) => c.is_active).map((c) => ({ value: c.id, label: `${c.full_name}${c.company_name ? ` — ${c.company_name}` : ""} (${c.email})` }))]}
            hint={enquiry ? "Creating the order links this enquiry to the selected customer." : undefined}
          />
        )}
        <Field label="Division" as="select" required={!enquiry} value={form.division_id} onChange={set("division_id")} options={[{ value: "", label: enquiry ? "Same as enquiry" : "Select a division" }, ...businessDivisions.map((d) => ({ value: d.id, label: d.name }))]} />
        <Field label="Product / description" required={!enquiry} maxLength={255} value={form.product_description} onChange={set("product_description")} hint={optional} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Quantity" type="number" min="0" step="0.01" inputMode="decimal" value={form.quantity} onChange={set("quantity")} hint={optional} />
          <Field label="Unit" maxLength={50} value={form.unit_of_measurement} onChange={set("unit_of_measurement")} placeholder="e.g. Metric tonnes" />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Order total" type="number" min="0" step="0.01" inputMode="decimal" value={form.total_amount} onChange={set("total_amount")} className="sm:col-span-2" hint="Optional. Shown to the customer." />
          <Field label="Currency" maxLength={3} value={form.currency} onChange={set("currency")} />
        </div>
        <Field label="Note to customer" as="textarea" maxLength={2000} value={form.customer_note} onChange={set("customer_note")} hint="Visible to the customer on the order." />
        <FormError message={error} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" busy={busy}>Create order</Button>
        </div>
      </form>
    </Dialog>
  );
}
