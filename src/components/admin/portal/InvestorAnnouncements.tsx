"use client";

import { useState, type FormEvent } from "react";
import { Megaphone } from "lucide-react";
import { useToast } from "@/hooks/useToast";
import { Button, Dialog, Empty, errorText, Field, FormError, fmtDate, Panel, Resource, StatusBadge, useResource } from "@/components/portal/ui";
import type { InvestorUpdate } from "@/types/portal";
import { useAdminApi } from "./useAdminApi";

/** Announcements addressed to every investor. Per-investor updates are managed on the investor's record. */
export function InvestorAnnouncements() {
  const { send } = useAdminApi();
  const { toast } = useToast();
  const updates = useResource<InvestorUpdate[]>("/admin/investor-updates");
  const [form, setForm] = useState<null | { title: string; body: string; is_published: boolean }>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>, success: string, after?: () => void) => {
    setError(null);
    setBusy(true);
    try {
      await action();
      toast.success(success);
      after?.();
      updates.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="Announcements to all investors"
      description="Visible to every investor once published. Do not include investment offers, projected returns or financial promises without client and legal approval."
      actions={<Button onClick={() => { setError(null); setForm({ title: "", body: "", is_published: false }); }}><Megaphone className="h-3.5 w-3.5" aria-hidden="true" /> New announcement</Button>}
    >
      <Resource state={updates} isEmpty={(d) => d.filter((u) => !u.investor_id).length === 0} empty={<Empty title="No announcements yet" />}>
        {(rows) => (
          <ul className="divide-y divide-line">
            {rows.filter((u) => !u.investor_id).map((u) => (
              <li key={u.id} className="flex flex-wrap items-start justify-between gap-3 py-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink [overflow-wrap:anywhere]">{u.title}</p>
                  <p className="mt-1 line-clamp-2 text-sm text-ink-muted [overflow-wrap:anywhere]">{u.body}</p>
                  <p className="mt-1 text-xs text-ink-subtle">Created {fmtDate(u.created_at)}{u.published_at ? ` · Published ${fmtDate(u.published_at)}` : ""}</p>
                </div>
                <span className="flex items-center gap-2">
                  <StatusBadge status={u.is_published ? "PUBLISHED" : "DRAFT"} />
                  <Button variant="ghost" className="min-h-8 px-3" disabled={busy} onClick={() => void run(() => send(`/admin/investor-updates/${u.id}`, "PATCH", { is_published: !u.is_published }), u.is_published ? "Announcement unpublished." : "Announcement published to all investors.")}>
                    {u.is_published ? "Unpublish" : "Publish"}
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Resource>

      <Dialog open={!!form} title="New announcement to all investors" onClose={() => setForm(null)} busy={busy}>
        {form && (
          <form
            className="space-y-4"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void run(() => send("/admin/investor-updates", "POST", { ...form, investor_id: null }), form.is_published ? "Announcement published." : "Announcement saved as a draft.", () => setForm(null));
            }}
          >
            <Field label="Title" required maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <Field label="Message" as="textarea" required maxLength={10000} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={form.is_published} onChange={(e) => setForm({ ...form, is_published: e.target.checked })} className="h-4 w-4 accent-[var(--eb-brand)]" />
              Publish to all investors immediately
            </label>
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setForm(null)} disabled={busy}>Cancel</Button>
              <Button type="submit" busy={busy}>Save announcement</Button>
            </div>
          </form>
        )}
      </Dialog>
    </Panel>
  );
}
