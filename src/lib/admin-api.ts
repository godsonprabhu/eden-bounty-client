/**
 * EDEN BOUNTY Sdn. Bhd. — Central Administrative API Client
 * Secure communication layer with FastAPI backend.
 *
 * Rules:
 * - Credentials ('include') enabled on all requests for HttpOnly cookie persistence.
 * - CSRF token passed via 'X-CSRF-Token' header on state-changing requests.
 * - Never persists CSRF tokens or session identifiers to localStorage/sessionStorage.
 */

import {
  AdminAssigneesEnvelope,
  AdminAssigneeSummary,
  AuditLogListEnvelope,
  AuditLogListQueryParams,
  AuditLogListResponseData,
  AdminOverviewEnvelope,
  AdminOverviewMetrics,
  AdminUser,
  AuthMeResponse,
  DashboardActivityEnvelope,
  DashboardActivityItem,
  EnquiryAssignmentPayload,
  EnquiryDetailEnvelope,
  EnquiryDetailResponseData,
  EnquiryListEnvelope,
  EnquiryListItem,
  EnquiryListQueryParams,
  EnquiryListResponseData,
  EnquiryNoteCreatePayload,
  EnquiryNoteItem,
  EnquiryNoteResponseEnvelope,
  EnquirySearchRequestBody,
  EnquiryStatusUpdatePayload,
  LoginCredentials,
  LoginResponse,
  LogoutResponse,
  MutationRequestOptions,
} from "@/types/admin";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export class AdminApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "AdminApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    return (await res.json()) as T;
  }

  let errorDetail = `Request failed with status ${res.status}`;
  try {
    const errorJson = await res.json();
    if (typeof errorJson.detail === "string") {
      errorDetail = errorJson.detail;
    } else if (Array.isArray(errorJson.detail) && errorJson.detail.length > 0) {
      errorDetail = errorJson.detail[0]?.msg || errorDetail;
    } else if (errorJson.message) {
      errorDetail = errorJson.message;
    }
  } catch {
    // Non-JSON response
    if (res.status === 401) {
      errorDetail = "Invalid email or password.";
    } else if (res.status === 403) {
      errorDetail = "Access forbidden. Insufficient permissions or invalid security token.";
    } else if (res.status === 404) {
      errorDetail = "The requested resource was not found.";
    } else if (res.status === 429) {
      errorDetail = "Too many requests. Please wait before retrying.";
    } else if (res.status >= 500) {
      errorDetail = "Internal server error. Please try again later.";
    }
  }

  // Intercept 401 Session Expiry on authenticated routes (excluding login attempts)
  if (typeof window !== "undefined" && res.status === 401) {
    const isLoginEndpoint = res.url ? res.url.includes("/api/v1/auth/login") : false;
    // An anonymous visitor on the sign-in page is expected to have no session.
    const isOnLoginPage = window.location.pathname === "/login";
    if (!isLoginEndpoint && !isOnLoginPage) {
      window.dispatchEvent(
        new CustomEvent("eb:session-expired", {
          detail: {
            reason: errorDetail || "Your administrative security session has expired. Re-authentication is required.",
            status: 401,
          },
        })
      );
    }
  }

  throw new AdminApiError(res.status, errorDetail);
}

/**
 * Authenticates an administrator with email and password.
 * Backend sets HttpOnly cookie 'eb_admin_session' and returns user profile + initial CSRF token.
 */
export async function apiLogin(credentials: LoginCredentials): Promise<{
  user: AdminUser;
  csrfToken: string;
  accountType: "ADMIN" | "CUSTOMER" | "INVESTOR";
  redirectTo: string;
}> {
  const url = `${API_BASE_URL}/api/v1/auth/login`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    credentials: "include",
    body: JSON.stringify({
      email: credentials.email.trim(),
      password: credentials.password,
    }),
  });

  const responseData = await handleResponse<LoginResponse>(res);
  const serverAccountType = responseData.data.account_type;
  let accountType: "ADMIN" | "CUSTOMER" | "INVESTOR" = "ADMIN";
  let redirectTo = "/admin";
  if (serverAccountType === "CUSTOMER") {
    accountType = "CUSTOMER";
    redirectTo = responseData.data.redirect_to || "/account";
  } else if (serverAccountType === "INVESTOR") {
    accountType = "INVESTOR";
    redirectTo = responseData.data.redirect_to || "/investors/portal";
  } else {
    redirectTo = responseData.data.redirect_to || "/admin";
  }

  return {
    user: responseData.data.user,
    csrfToken: responseData.data.csrf_token,
    accountType,
    redirectTo,
  };
}

/**
 * Restores the active administrator session from the HttpOnly session cookie.
 * Returns the administrator profile and the active session CSRF token for React in-memory hydration.
 */
export async function apiGetMe(): Promise<{
  user: AdminUser;
  csrfToken: string;
}> {
  const url = `${API_BASE_URL}/api/v1/auth/me`;

  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
  });

  const responseData = await handleResponse<AuthMeResponse>(res);
  const { csrf_token, ...user } = responseData.data;
  return {
    user,
    csrfToken: csrf_token,
  };
}

/**
 * Logs out the administrator by invalidating the server-side session and clearing the cookie.
 * Requires the active in-memory CSRF token.
 */
export async function apiLogout(csrfToken: string | null): Promise<void> {
  const url = `${API_BASE_URL}/api/v1/auth/logout`;

  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const res = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
  });

  // Even if backend logout fails with 401 (e.g. session already expired), consider client logged out
  if (!res.ok && res.status !== 401 && res.status !== 403) {
    await handleResponse<LogoutResponse>(res);
  }
}

/**
 * Fetches high-level pipeline volume metrics from GET /api/v1/admin/dashboard/overview.
 */
export async function apiGetDashboardOverview(): Promise<AdminOverviewMetrics> {
  const url = `${API_BASE_URL}/api/v1/admin/dashboard/overview`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
  });
  const data = await handleResponse<AdminOverviewEnvelope>(res);
  return data.data;
}

/**
 * Fetches recent commercial enquiries from GET /api/v1/admin/rfqs with limit and sort.
 * Overview is strictly read-only and limited to 5 records.
 */
export async function apiGetRecentEnquiries(limit: number = 5): Promise<EnquiryListItem[]> {
  const url = `${API_BASE_URL}/api/v1/admin/rfqs?limit=${limit}&sort_by=created_at&sort_order=desc`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
  });
  const data = await handleResponse<EnquiryListEnvelope>(res);
  return data.data.items;
}

/**
 * Fetches recent non-sensitive operational activity from GET /api/v1/admin/dashboard/activity.
 */
export async function apiGetDashboardActivity(limit: number = 10): Promise<DashboardActivityItem[]> {
  const url = `${API_BASE_URL}/api/v1/admin/dashboard/activity?limit=${limit}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
  });
  const data = await handleResponse<DashboardActivityEnvelope>(res);
  return data.data;
}

/**
 * Fetches the SUPER_ADMIN-only paginated audit ledger from GET /api/v1/admin/audit-logs.
 */
export async function apiGetAuditLogs(
  params: AuditLogListQueryParams = {},
  options?: { signal?: AbortSignal }
): Promise<AuditLogListResponseData> {
  const searchParams = new URLSearchParams();

  if (params.page !== undefined) searchParams.set("page", params.page.toString());
  if (params.limit !== undefined) searchParams.set("limit", params.limit.toString());
  if (params.action?.trim()) searchParams.set("action", params.action.trim());
  if (params.entity_table?.trim()) {
    searchParams.set("entity_table", params.entity_table.trim());
  }

  const query = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/admin/audit-logs${query ? `?${query}` : ""}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
    signal: options?.signal,
  });
  const envelope = await handleResponse<AuditLogListEnvelope>(res);
  return envelope.data;
}

/**
 * Fetches paginated, filtered, and sorted commercial enquiries from GET /api/v1/admin/rfqs.
 */
export async function apiListEnquiries(
  params: EnquiryListQueryParams = {},
  options?: { signal?: AbortSignal }
): Promise<EnquiryListResponseData> {
  const searchParams = new URLSearchParams();

  if (params.page !== undefined && params.page !== null) {
    searchParams.set("page", params.page.toString());
  }
  if (params.limit !== undefined && params.limit !== null) {
    searchParams.set("limit", params.limit.toString());
  }
  if (params.division_id) {
    searchParams.set("division_id", params.division_id.trim());
  }
  if (params.status) {
    searchParams.set("status", params.status.trim());
  }
  if (params.assigned_admin_id) {
    searchParams.set("assigned_admin_id", params.assigned_admin_id.trim());
  }
  if (params.search) {
    searchParams.set("search", params.search.trim());
  }
  if (params.sort_by) {
    searchParams.set("sort_by", params.sort_by);
  }
  if (params.sort_order) {
    searchParams.set("sort_order", params.sort_order);
  }
  if (params.created_from) {
    searchParams.set("created_from", params.created_from);
  }
  if (params.created_to) {
    searchParams.set("created_to", params.created_to);
  }

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/admin/rfqs${queryString ? `?${queryString}` : ""}`;

  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
    signal: options?.signal,
  });

  const data = await handleResponse<EnquiryListEnvelope>(res);
  return data.data;
}

/**
 * Executes a privacy-preserving authenticated POST search query for commercial enquiries.
 * Transmits search terms and filter criteria within an encrypted JSON request body.
 * SEC-01 Hardening: Zero search terms appear in URLs, browser history, or web server access logs.
 * Requires administrator session and CSRF token.
 */
export async function apiSearchEnquiries(
  body: EnquirySearchRequestBody,
  csrfToken: string | null,
  options?: { signal?: AbortSignal }
): Promise<EnquiryListResponseData> {
  const url = `${API_BASE_URL}/api/v1/admin/rfqs/search`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const res = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
    signal: options?.signal,
  });

  const data = await handleResponse<EnquiryListEnvelope>(res);
  return data.data;
}

/**
 * Fetches active administrators directory for filter selector from GET /api/v1/admin/administrators.
 */
export async function apiGetAdministrators(): Promise<AdminAssigneeSummary[]> {
  const url = `${API_BASE_URL}/api/v1/admin/administrators`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
  });
  const data = await handleResponse<AdminAssigneesEnvelope>(res);
  return data.data;
}

/**
 * Fetches complete commercial enquiry dossier and timelines from GET /api/v1/admin/rfqs/{id}.
 * Stage 4.2: Authorized administrative read access for SUPER_ADMIN and OPERATIONS_ADMIN.
 * Network metadata (source_ip, client_user_agent) is scrubbed.
 */
export async function apiGetEnquiryDetail(id: string): Promise<EnquiryDetailResponseData> {
  const url = `${API_BASE_URL}/api/v1/admin/rfqs/${encodeURIComponent(id)}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "include",
  });
  const data = await handleResponse<EnquiryDetailEnvelope>(res);
  return data.data;
}

/**
 * Phase C13.4 Stage 4.3: Operational Workflow Mutations
 */

/**
 * Assigns or unassigns an enquiry to an active central administrator.
 * Division remains strictly locked in the backend.
 *
 * Endpoint: POST /api/v1/admin/rfqs/{id}/assign
 *
 * Requirements:
 * - Credentials ('include') for HttpOnly session cookie.
 * - CSRF token passed via 'X-CSRF-Token' header.
 * - Never silently retries failed mutations.
 * - Returns refreshed EnquiryDetailResponseData.
 */
export async function apiAssignEnquiry(
  id: string,
  payload: EnquiryAssignmentPayload,
  csrfToken: string | null,
  options?: MutationRequestOptions
): Promise<EnquiryDetailResponseData> {
  if (!csrfToken) {
    throw new AdminApiError(403, "CSRF security token is missing or expired. Please refresh the page.");
  }

  const url = `${API_BASE_URL}/api/v1/admin/rfqs/${encodeURIComponent(id)}/assign`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRF-Token": csrfToken,
    },
    credentials: "include",
    signal: options?.signal,
    body: JSON.stringify({
      assigned_admin_id: payload.assigned_admin_id,
      assignment_rationale: payload.assignment_rationale?.trim() || null,
    }),
  });

  const envelope = await handleResponse<EnquiryDetailEnvelope>(res);
  return envelope.data;
}

/**
 * Transitions the enquiry lifecycle status according to the authoritative state transition matrix.
 * Mandatory change_reason must be between 3 and 1000 characters.
 * Reopening terminal statuses requires SUPER_ADMIN authority.
 *
 * Endpoint: PATCH /api/v1/admin/rfqs/{id}/status
 *
 * Requirements:
 * - Credentials ('include') for HttpOnly session cookie.
 * - CSRF token passed via 'X-CSRF-Token' header.
 * - Never silently retries failed mutations.
 * - Returns refreshed EnquiryDetailResponseData.
 */
export async function apiUpdateEnquiryStatus(
  id: string,
  payload: EnquiryStatusUpdatePayload,
  csrfToken: string | null,
  options?: MutationRequestOptions
): Promise<EnquiryDetailResponseData> {
  if (!csrfToken) {
    throw new AdminApiError(403, "CSRF security token is missing or expired. Please refresh the page.");
  }

  const url = `${API_BASE_URL}/api/v1/admin/rfqs/${encodeURIComponent(id)}/status`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRF-Token": csrfToken,
    },
    credentials: "include",
    signal: options?.signal,
    body: JSON.stringify({
      new_status: payload.new_status.trim().toUpperCase(),
      change_reason: payload.change_reason.trim(),
    }),
  });

  const envelope = await handleResponse<EnquiryDetailEnvelope>(res);
  return envelope.data;
}

/**
 * Appends an internal operational follow-up note to an enquiry.
 * Notes are strictly append-only; editing and deletion are prohibited.
 *
 * Endpoint: POST /api/v1/admin/rfqs/{id}/notes
 *
 * Requirements:
 * - Credentials ('include') for HttpOnly session cookie.
 * - CSRF token passed via 'X-CSRF-Token' header.
 * - Never silently retries failed mutations.
 * - Returns created EnquiryNoteItem.
 */
export async function apiAddEnquiryNote(
  id: string,
  payload: EnquiryNoteCreatePayload,
  csrfToken: string | null,
  options?: MutationRequestOptions
): Promise<EnquiryNoteItem> {
  if (!csrfToken) {
    throw new AdminApiError(403, "CSRF security token is missing or expired. Please refresh the page.");
  }

  const url = `${API_BASE_URL}/api/v1/admin/rfqs/${encodeURIComponent(id)}/notes`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRF-Token": csrfToken,
    },
    credentials: "include",
    signal: options?.signal,
    body: JSON.stringify({
      note_text: payload.note_text.trim(),
    }),
  });

  const envelope = await handleResponse<EnquiryNoteResponseEnvelope>(res);
  return envelope.data;
}
