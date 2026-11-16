"use client";

import { use, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowLeft, Plus } from "lucide-react";
import { useAdminApi } from "@/components/admin/portal/useAdminApi";
import { ShipmentCard, StatusTimeline } from "@/components/portal/OrderViews";
import { Button, DefinitionList, Dialog, Empty, errorText, Field, FormError, fmtDateTime, fmtMoney, fmtQuantity, humanize, PageHeader, Panel, Resource, StatusBadge, useResource } from "@/components/portal/ui";
import { useToast } from "@/hooks/useToast";
import { ORDER_STATUSES, SHIPMENT_STATUSES, type AdminOrderDetail, type Shipment } from "@/types/portal";

const blankShipment = { id: "", carrier: "", tracking_number: "", origin: "", destination: "", status: "PREPARING", estimated_delivery_on: "" };

export default function AdminOrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { send } = useAdminApi();
  const { toast } = useToast();
  const order = useResource<AdminOrderDetail>(`/admin/orders/${encodeURIComponent(id)}`);

  const [statusForm, setStatusForm] = useState<null | { new_status: string; note: string }>(null);
  const [shipment, setShipment] = useState<null | typeof blankShipment>(null);
  const [event, setEvent] = useState<null | { shipment_id: string; description: string; location: string }>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>, success: string, after: () => void) => {
    setError(null);
    setBusy(true);
    try {
      await action();
      toast.success(success);
      after();
      order.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const editShipment = (s: Shipment) => {
    setError(null);
    setShipment({ id: s.id, carrier: s.carrier ?? "", tracking_number: s.tracking_number ?? "", origin: s.origin ?? "", destination: s.destination ?? "", status: s.status, estimated_delivery_on: s.estimated_delivery_on ?? "" });
  };

  const saveShipment = (e: FormEvent) => {
    e.preventDefault();
    if (!shipment) return;
    const { id: shipmentId, estimated_delivery_on, ...fields } = shipment;
    const now = new Date().toISOString();
    const body: Record<string, unknown> = { ...fields, estimated_delivery_on: estimated_delivery_on || null };
    if (fields.status === "SHIPPED" || fields.status === "IN_TRANSIT") body.shipped_at = now;
    if (fields.status === "DELIVERED") body.delivered_at = now;
    void run(
      () => (shipmentId ? send(`/admin/shipments/${shipmentId}`, "PATCH", body) : send(`/admin/orders/${id}/shipments`, "POST", body)),
      shipmentId ? "Shipment updated." : "Shipment added.",
      () => setShipment(null)
    );
  };

  return (
    <div className="space-y-6">
      <Link href="/admin/orders" className="inline-flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.16em] text-ink-muted hover:text-brand">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> All orders
      </Link>
      <Resource state={order}>
        {(o) => (
          <>
            <PageHeader
              eyebrow="Order"
              title={o.reference_number}
              intro={o.product_description}
              actions={
                <>
                  <StatusBadge status={o.status} />
                  <Button onClick={() => { setError(null); setStatusForm({ new_status: ORDER_STATUSES.find((s) => s !== o.status) ?? "PROCESSING", note: "" }); }}>Update status</Button>
                </>
              }
            />
            <div className="grid gap-6 lg:grid-cols-5">
              <Panel title="Order details" className="lg:col-span-3">
                <DefinitionList
                  items={[
                    ["Customer", <Link key="c" href={`/admin/customers/${o.customer.id}`} className="underline decoration-brand underline-offset-4 hover:text-brand">{o.customer.full_name} ({o.customer.email})</Link>],
                    ["Service", o.division.name],
                    ["Quantity", fmtQuantity(o.quantity, o.unit_of_measurement)],
                    ["Order total", fmtMoney(o.total_amount, o.currency)],
                    ["Created", fmtDateTime(o.created_at)],
                    ["From enquiry", o.enquiry_id ? <Link key="e" href={`/admin/enquiries/${o.enquiry_id}`} className="font-mono text-xs underline decoration-brand underline-offset-4 hover:text-brand">{o.enquiry_reference}</Link> : null],
                    ["Note to customer", o.customer_note],
                  ]}
                />
              </Panel>
              <Panel title="Status history" description="Visible to the customer." className="lg:col-span-2">
                <StatusTimeline events={o.status_history} />
              </Panel>
            </div>

            <Panel title="Shipments and tracking" description="Everything here is visible to the customer." actions={<Button onClick={() => { setError(null); setShipment(blankShipment); }}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add shipment</Button>}>
              {o.shipments.length === 0 ? (
                <Empty title="No shipment recorded">Add a shipment when the order is dispatched, then record tracking updates against it.</Empty>
              ) : (
                <div className="grid gap-5 lg:grid-cols-2">
                  {o.shipments.map((s, i) => (
                    <ShipmentCard
                      key={s.id}
                      shipment={s}
                      index={i}
                      footer={
                        <div className="flex flex-wrap gap-2">
                          <Button variant="ghost" className="min-h-9" onClick={() => editShipment(s)}>Edit shipment</Button>
                          <Button variant="ghost" className="min-h-9" onClick={() => { setError(null); setEvent({ shipment_id: s.id, description: "", location: "" }); }}>Add tracking update</Button>
                        </div>
                      }
                    />
                  ))}
                </div>
              )}
            </Panel>

            <Dialog open={!!statusForm} title="Update order status" onClose={() => setStatusForm(null)} busy={busy}>
              {statusForm && (
                <form
                  className="space-y-4"
                  onSubmit={(e: FormEvent) => {
                    e.preventDefault();
                    void run(() => send(`/admin/orders/${id}/status`, "PATCH", statusForm), "Order status updated.", () => setStatusForm(null));
                  }}
                >
                  <Field label="New status" as="select" value={statusForm.new_status} onChange={(e) => setStatusForm({ ...statusForm, new_status: e.target.value })} options={ORDER_STATUSES.filter((s) => s !== o.status).map((s) => ({ value: s, label: humanize(s) }))} />
                  <Field label="Note to customer" as="textarea" maxLength={1000} value={statusForm.note} onChange={(e) => setStatusForm({ ...statusForm, note: e.target.value })} hint="Optional. Shown to the customer in the order history." />
                  <FormError message={error} />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setStatusForm(null)} disabled={busy}>Cancel</Button>
                    <Button type="submit" busy={busy}>Update status</Button>
                  </div>
                </form>
              )}
            </Dialog>

            <Dialog open={!!shipment} title={shipment?.id ? "Edit shipment" : "Add shipment"} onClose={() => setShipment(null)} busy={busy}>
              {shipment && (
                <form onSubmit={saveShipment} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Carrier" maxLength={150} value={shipment.carrier} onChange={(e) => setShipment({ ...shipment, carrier: e.target.value })} />
                    <Field label="Tracking number" maxLength={120} value={shipment.tracking_number} onChange={(e) => setShipment({ ...shipment, tracking_number: e.target.value })} />
                    <Field label="From" maxLength={150} value={shipment.origin} onChange={(e) => setShipment({ ...shipment, origin: e.target.value })} />
                    <Field label="To" maxLength={150} value={shipment.destination} onChange={(e) => setShipment({ ...shipment, destination: e.target.value })} />
                    <Field label="Shipment status" as="select" value={shipment.status} onChange={(e) => setShipment({ ...shipment, status: e.target.value })} options={SHIPMENT_STATUSES.map((s) => ({ value: s, label: humanize(s) }))} />
                    <Field label="Estimated delivery" type="date" value={shipment.estimated_delivery_on} onChange={(e) => setShipment({ ...shipment, estimated_delivery_on: e.target.value })} />
                  </div>
                  <FormError message={error} />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setShipment(null)} disabled={busy}>Cancel</Button>
                    <Button type="submit" busy={busy}>{shipment.id ? "Save shipment" : "Add shipment"}</Button>
                  </div>
                </form>
              )}
            </Dialog>

            <Dialog open={!!event} title="Add tracking update" onClose={() => setEvent(null)} busy={busy}>
              {event && (
                <form
                  className="space-y-4"
                  onSubmit={(e: FormEvent) => {
                    e.preventDefault();
                    void run(() => send(`/admin/shipments/${event.shipment_id}/events`, "POST", { description: event.description, location: event.location }), "Tracking update added.", () => setEvent(null));
                  }}
                >
                  <Field label="Update" required maxLength={500} value={event.description} onChange={(e) => setEvent({ ...event, description: e.target.value })} placeholder="e.g. Departed origin port" />
                  <Field label="Location" maxLength={150} value={event.location} onChange={(e) => setEvent({ ...event, location: e.target.value })} />
                  <FormError message={error} />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setEvent(null)} disabled={busy}>Cancel</Button>
                    <Button type="submit" busy={busy}>Add update</Button>
                  </div>
                </form>
              )}
            </Dialog>
          </>
        )}
      </Resource>
    </div>
  );
}
