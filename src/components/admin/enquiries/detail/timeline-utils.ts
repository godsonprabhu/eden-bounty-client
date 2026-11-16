import { EnquiryDetailResponseData, EnquiryTimelineEvent, TimelineEventType } from "@/types/admin";

export type TimelineSortOrder = "desc" | "asc";

/**
 * Synthesizes a unified, deterministically ordered operational timeline stream
 * from enquiry submission, status changes, assignments, and internal notes.
 *
 * Rules:
 * - Default: Newest first (descending UTC timestamp).
 * - Toggleable: Oldest first (ascending UTC timestamp).
 * - Exact tie-breaker when timestamps match: NOTE > STATUS_CHANGE > ASSIGNMENT > SUBMISSION.
 * - Final tie-breaker: Namespaced event ID string comparison.
 * - Timestamps are normalized to ISO 8601 UTC.
 */
export function synthesizeEnquiryTimeline(
  dossier: EnquiryDetailResponseData,
  sortOrder: TimelineSortOrder = "desc"
): EnquiryTimelineEvent[] {
  const events: EnquiryTimelineEvent[] = [];

  // 1. Initial Submission Event
  events.push({
    eventId: `sub-${dossier.id}`,
    eventType: "SUBMISSION",
    timestamp: dossier.created_at,
    title: "Commercial Enquiry Submitted",
    description: `Submitted by ${dossier.full_name} representing ${dossier.company_name} (${dossier.country}) under ${dossier.current_division.name}.`,
    actorName: dossier.full_name,
    actorEmail: dossier.business_email,
    metadata: {
      productFocus: dossier.product_focus,
      referenceNumber: dossier.reference_number,
      country: dossier.country,
    },
  });

  // 2. Lifecycle Status Transitions
  for (const s of dossier.status_history || []) {
    events.push({
      eventId: `status-${s.id}`,
      eventType: "STATUS_CHANGE",
      timestamp: s.created_at,
      title: `Status Transition: ${formatStatusName(s.old_status)} → ${formatStatusName(s.new_status)}`,
      description: s.change_reason || "No transition rationale recorded.",
      actorName: s.changed_by_admin?.name || "System Administrator",
      actorEmail: s.changed_by_admin?.email,
      metadata: {
        oldStatus: s.old_status,
        newStatus: s.new_status,
      },
    });
  }

  // 3. Administrative Assignments & Transfers
  for (const a of dossier.assignments || []) {
    const prev = a.previous_admin?.name || "Unassigned";
    const next = a.new_admin?.name || "Unassigned";
    events.push({
      eventId: `assign-${a.id}`,
      eventType: "ASSIGNMENT",
      timestamp: a.assigned_at,
      title: `Operational Assignment: ${prev} → ${next}`,
      description: a.assignment_rationale || "No assignment rationale recorded.",
      actorName: a.assigned_by_admin?.name || "Operations Lead",
      actorEmail: a.assigned_by_admin?.email,
      metadata: {
        previousAdmin: a.previous_admin,
        newAdmin: a.new_admin,
      },
    });
  }

  // 4. Internal Operational Notes
  for (const n of dossier.notes || []) {
    events.push({
      eventId: `note-${n.id}`,
      eventType: "NOTE",
      timestamp: n.created_at,
      title: "Internal Operational Note",
      description: n.note_text,
      actorName: n.author_admin?.name || "Operations Administrator",
      actorEmail: n.author_admin?.email,
      metadata: {
        isInternalOnly: n.is_internal_only,
      },
    });
  }

  // Event type priority tie-breaker when timestamps are identical
  const typePriority: Record<TimelineEventType, number> = {
    NOTE: 1,
    STATUS_CHANGE: 2,
    ASSIGNMENT: 3,
    SUBMISSION: 4,
  };

  return events.sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime();
    const timeB = new Date(b.timestamp).getTime();

    if (timeA !== timeB) {
      return sortOrder === "desc" ? timeB - timeA : timeA - timeB;
    }

    // Identical timestamp: tie-break by event type priority
    const prioA = typePriority[a.eventType] || 99;
    const prioB = typePriority[b.eventType] || 99;
    if (prioA !== prioB) {
      return prioA - prioB;
    }

    // Final tie-breaker: namespaced event ID lexicographical order
    return a.eventId.localeCompare(b.eventId);
  });
}

function formatStatusName(status: string): string {
  const map: Record<string, string> = {
    NEW: "New Intake",
    UNDER_REVIEW: "Under Review",
    ASSIGNED: "Assigned",
    IN_COMMUNICATION: "In Communication",
    QUOTATION_PENDING: "Quotation Pending",
    COMPLETED: "Completed",
    DECLINED: "Declined",
    ARCHIVED: "Archived",
  };
  return map[status] || status;
}
