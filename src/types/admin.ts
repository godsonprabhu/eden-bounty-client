/**
 * EDEN BOUNTY Sdn. Bhd. — Central Administrative Console
 * Types and Interfaces for Phase C13.4 Admin Platform
 */

export type AdminRoleType = "SUPER_ADMIN" | "OPERATIONS_ADMIN";

export interface AdminUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  roles: string[];
  last_login_at?: string | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponseData {
  user: AdminUser;
  csrf_token: string;
  /** Decided by the server from the authenticated account. */
  account_type?: "ADMIN" | "CUSTOMER" | "INVESTOR";
  redirect_to?: string;
}

/** Result of a sign-in on the main login page. */
export interface LoginResult {
  accountType: "ADMIN" | "CUSTOMER" | "INVESTOR";
  redirectTo: string;
}

export interface LoginResponse {
  success: boolean;
  data: LoginResponseData;
}

export interface AuthMeResponseData extends AdminUser {
  csrf_token: string;
}

export interface AuthMeResponse {
  success: boolean;
  data: AuthMeResponseData;
}

export interface LogoutResponse {
  success: boolean;
  message: string;
}

export interface AdminApiError {
  detail: string;
  status: number;
}

// ==============================================================================
// Phase C13.4 Stage 3: Dashboard Overview & Activity Types
// ==============================================================================

export interface DivisionMetricItem {
  division_id: string;
  code: string;
  name: string;
  count: number;
  is_active?: boolean;
}

export interface AdminOverviewMetrics {
  total_enquiries: number;
  by_status: Record<string, number>;
  by_division: DivisionMetricItem[];
  unassigned_count: number;
  today_count: number;
}

export interface AdminOverviewEnvelope {
  success: boolean;
  data: AdminOverviewMetrics;
}

export interface DashboardActivityItem {
  id: string;
  event_type: "STATUS_CHANGED" | "ENQUIRY_ASSIGNED" | "ENQUIRY_UNASSIGNED" | string;
  reference_number: string;
  division_name: string;
  description: string;
  actor_name: string;
  timestamp: string;
}

export interface DashboardActivityEnvelope {
  success: boolean;
  data: DashboardActivityItem[];
}

export interface AuditLogListItem {
  id: number;
  timestamp: string;
  actor_admin_id: string | null;
  actor_email: string | null;
  ip_address: string | null;
  action: string;
  entity_table: string;
  entity_id: string;
  old_state: Record<string, unknown> | null;
  new_state: Record<string, unknown> | null;
  client_user_agent: string | null;
}

export interface AuditLogPaginationMetadata {
  page: number;
  limit: number;
  total_items: number;
  total_pages: number;
}

export interface AuditLogListResponseData {
  items: AuditLogListItem[];
  pagination: AuditLogPaginationMetadata;
}

export interface AuditLogListEnvelope {
  success: boolean;
  data: AuditLogListResponseData;
}

export interface AuditLogListQueryParams {
  page?: number;
  limit?: number;
  action?: string;
  entity_table?: string;
}

export interface AdminAssignedUserSummary {
  id: string;
  name: string;
  email: string;
  job_title?: string | null;
}

export interface EnquiryListItem {
  id: string;
  reference_number: string;
  created_at: string;
  company_name: string;
  country: string;
  division_id: string;
  division_name: string;
  product_focus: string;
  status: string;
  assigned_admin: AdminAssignedUserSummary | null;
}

export interface EnquirySearchRequestBody {
  page?: number;
  limit?: number;
  division_id?: string;
  status?: string;
  assigned_admin_id?: string;
  search?: string;
  sort_by?: "created_at" | "reference_number" | "company_name" | "status";
  sort_order?: "asc" | "desc";
  created_from?: string;
  created_to?: string;
}

export interface EnquiryListResponseData {
  items: EnquiryListItem[];
  pagination: {
    page: number;
    limit: number;
    total_items: number;
    total_pages: number;
  };
}

export interface EnquiryListEnvelope {
  success: boolean;
  data: EnquiryListResponseData;
}

export interface EnquiryListQueryParams {
  page?: number;
  limit?: number;
  division_id?: string;
  status?: string;
  assigned_admin_id?: string;
  search?: string;
  sort_by?: "created_at" | "reference_number" | "company_name" | "status";
  sort_order?: "asc" | "desc";
  created_from?: string;
  created_to?: string;
}

export interface AdminAssigneeSummary {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  roles: string[];
}

export interface AdminAssigneesEnvelope {
  success: boolean;
  data: AdminAssigneeSummary[];
}

export interface DivisionSummary {
  id: string;
  code: string;
  name: string;
  accent_color?: string | null;
}

export interface EnquiryAssignmentHistoryItem {
  id: string;
  previous_admin: AdminAssignedUserSummary | null;
  new_admin: AdminAssignedUserSummary | null;
  assigned_by_admin: AdminAssignedUserSummary;
  assignment_rationale: string | null;
  assigned_at: string;
}

export interface EnquiryStatusHistoryItem {
  id: string;
  old_status: string;
  new_status: string;
  change_reason: string | null;
  changed_by_admin: AdminAssignedUserSummary;
  created_at: string;
}

export interface EnquiryNoteItem {
  id: string;
  author_admin: AdminAssignedUserSummary;
  note_text: string;
  is_internal_only: boolean;
  created_at: string;
}

// ==============================================================================
// Phase C13.4 Stage 4.3: Operational Workflow Mutation Payloads & Responses
// ==============================================================================

export interface EnquiryAssignmentPayload {
  assigned_admin_id: string | null;
  assignment_rationale?: string | null;
}

export interface EnquiryStatusUpdatePayload {
  new_status: string;
  change_reason: string;
}

export interface EnquiryNoteCreatePayload {
  note_text: string;
}

export interface EnquiryNoteResponseEnvelope {
  success: boolean;
  data: EnquiryNoteItem;
}

export interface MutationRequestOptions {
  signal?: AbortSignal;
}

/**
 * Authoritative lifecycle status transition matrix from backend schema.
 * Reopening terminal statuses requires SUPER_ADMIN authority.
 */
export const PERMITTED_STATUS_TRANSITIONS: Record<string, string[]> = {
  NEW: ["UNDER_REVIEW", "ASSIGNED", "DECLINED"],
  UNDER_REVIEW: ["ASSIGNED", "IN_COMMUNICATION", "DECLINED"],
  ASSIGNED: ["UNDER_REVIEW", "IN_COMMUNICATION", "QUOTATION_PENDING", "DECLINED"],
  IN_COMMUNICATION: ["UNDER_REVIEW", "QUOTATION_PENDING", "COMPLETED", "DECLINED", "ARCHIVED"],
  QUOTATION_PENDING: ["IN_COMMUNICATION", "COMPLETED", "DECLINED", "ARCHIVED"],
  COMPLETED: ["ARCHIVED", "IN_COMMUNICATION", "QUOTATION_PENDING"],
  DECLINED: ["ARCHIVED", "UNDER_REVIEW"],
  ARCHIVED: ["UNDER_REVIEW"],
};

export const SUPER_ADMIN_REQUIRED_TRANSITIONS: ReadonlySet<string> = new Set([
  "COMPLETED->IN_COMMUNICATION",
  "COMPLETED->QUOTATION_PENDING",
  "DECLINED->UNDER_REVIEW",
  "ARCHIVED->UNDER_REVIEW",
]);

export interface EnquiryDetailResponseData {
  id: string;
  reference_number: string;
  status: string;
  created_at: string;
  updated_at: string;
  full_name: string;
  company_name: string;
  business_email: string;
  contact_number: string | null;
  country: string;
  initial_division: DivisionSummary;
  current_division: DivisionSummary;
  product_focus: string;
  quantity: number | string | null;
  unit_of_measurement: string | null;
  specifications: string | null;
  additional_notes: string | null;
  preferred_incoterm: string | null;
  target_destination_port: string | null;
  assigned_admin: AdminAssignedUserSummary | null;
  assignments: EnquiryAssignmentHistoryItem[];
  status_history: EnquiryStatusHistoryItem[];
  notes: EnquiryNoteItem[];
}

export interface EnquiryDetailEnvelope {
  success: boolean;
  data: EnquiryDetailResponseData;
}

export type TimelineEventType = "SUBMISSION" | "STATUS_CHANGE" | "ASSIGNMENT" | "NOTE";

export interface EnquiryTimelineEvent {
  eventId: string;
  eventType: TimelineEventType;
  timestamp: string;
  title: string;
  description?: string | null;
  actorName: string;
  actorEmail?: string | null;
  actorRole?: string | null;
  metadata?: Record<string, unknown>;
}
