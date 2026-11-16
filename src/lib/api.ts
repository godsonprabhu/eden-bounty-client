/**
 * Small typed client for the customer portal, investor portal and the newer admin screens.
 *
 * - Always sends the HttpOnly session cookie (`credentials: "include"`); tokens are never read
 *   or stored by JavaScript.
 * - State-changing requests carry the per-session CSRF token in `X-CSRF-Token`.
 * - Authorisation is decided by the API. Nothing here grants access; a 401/403 is simply surfaced.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON body. */
  body?: unknown;
  /** Raw body (file upload); sent as-is with `contentType`. */
  raw?: Blob;
  contentType?: string;
  csrf?: string | null;
  signal?: AbortSignal;
}

const FALLBACK: Record<number, string> = {
  401: "Your session has ended. Please sign in again.",
  403: "You do not have permission to do that.",
  404: "The requested record was not found.",
  409: "That conflicts with an existing record.",
  413: "The file is too large.",
  415: "That file type is not accepted.",
  429: "Too many attempts. Please wait a few minutes and try again.",
};

export function apiUrl(path: string): string {
  return `${API_BASE_URL}/api/v1${path}`;
}

/** Calls the API and returns the `data` member of the response envelope (or the whole body if there is none). */
export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, raw, contentType, csrf, signal } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (raw) headers["Content-Type"] = contentType || "application/octet-stream";
  else if (body !== undefined) headers["Content-Type"] = "application/json";
  if (csrf) headers["X-CSRF-Token"] = csrf;

  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method,
      headers,
      credentials: "include",
      body: raw ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal,
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "Unable to reach the server. Please check your connection and try again.");
  }

  if (res.ok) {
    const json = (await res.json().catch(() => ({}))) as { data?: T };
    return (json && typeof json === "object" && "data" in json ? json.data : json) as T;
  }

  let detail = FALLBACK[res.status] || (res.status >= 500 ? "Something went wrong on our side. Please try again." : `Request failed (${res.status}).`);
  try {
    const json = await res.json();
    if (typeof json.detail === "string") detail = json.detail;
    else if (Array.isArray(json.detail) && json.detail[0]?.msg) detail = String(json.detail[0].msg).replace(/^Value error, /, "");
  } catch {
    /* non-JSON error body */
  }

  if (res.status === 401 && typeof window !== "undefined") {
    const area = path.startsWith("/admin") ? "admin" : path.startsWith("/investor") ? "investor" : "customer";
    if (area === "admin") {
      window.dispatchEvent(new CustomEvent("eb:session-expired", { detail: { reason: detail, status: 401 } }));
    } else {
      window.dispatchEvent(new CustomEvent("eb:portal-unauthorized", { detail: { area } }));
    }
  }
  throw new ApiError(res.status, detail);
}
