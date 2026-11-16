import { NextResponse, type NextRequest } from "next/server";

/**
 * 1. Content-Security-Policy (security remediation, finding 3).
 *
 *    Every page response carries a policy with a fresh per-request nonce. Next.js reads the nonce
 *    from the request's CSP header and puts it on its own scripts; the root layout puts it on the
 *    one inline script of our own (theme initialisation). 'strict-dynamic' lets those trusted
 *    scripts load the page's chunks, while injected inline or third-party scripts are refused.
 *    Pages are therefore rendered per request (a nonce cannot be baked into static HTML).
 *
 *    The site loads nothing from other origins (fonts are self-hosted by next/font, Three.js is
 *    bundled and draws to a canvas), so every fetch directive is 'self'. Styles keep
 *    'unsafe-inline' because Motion and React set element style attributes, which nonces cannot
 *    cover; style injection is far less dangerous than script injection.
 *
 *    CSP_MODE=enforce (default) | report-only | off. Use report-only for a first production
 *    deploy if desired; CSP_REPORT_URI (optional) receives violation reports.
 *
 * 2. Defence-in-depth gate for the three signed-in areas.
 *
 *    Without the matching session cookie the visitor is redirected to the right sign-in page
 *    before any dashboard shell is served. This is a presence check only and is NOT the security
 *    control: every API call is authenticated and authorised server-side by FastAPI (session
 *    lookup, expiry, role and ownership checks), so a forged or mismatched cookie yields no data.
 */
const AREAS: Array<{ prefix: string; cookie: string; login: string; returnUrl: boolean }> = [
  { prefix: "/admin", cookie: process.env.ADMIN_SESSION_COOKIE_NAME || "eb_admin_session", login: "/login", returnUrl: true },
  { prefix: "/account", cookie: process.env.CUSTOMER_SESSION_COOKIE_NAME || "eb_customer_session", login: "/login", returnUrl: false },
  { prefix: "/investors/portal", cookie: process.env.INVESTOR_SESSION_COOKIE_NAME || "eb_investor_session", login: "/investors/login", returnUrl: false },
];

function buildContentSecurityPolicy(nonce: string, isDev: boolean, reportUri?: string): string {
  const directives = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${isDev ? " ws: wss:" : ""}`,
    "media-src 'self'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "frame-src 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  if (reportUri) directives.push(`report-uri ${reportUri}`);
  return directives.join("; ");
}

function cspMode(): "enforce" | "report-only" | "off" {
  const mode = (process.env.CSP_MODE || "enforce").trim().toLowerCase();
  return mode === "report-only" || mode === "off" ? mode : "enforce";
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const area = AREAS.find((a) => pathname === a.prefix || pathname.startsWith(`${a.prefix}/`));
  if (area && !request.cookies.has(area.cookie)) {
    const url = request.nextUrl.clone();
    url.pathname = area.login;
    url.search = area.returnUrl ? `?returnUrl=${encodeURIComponent(pathname + search)}` : "";
    return NextResponse.redirect(url);
  }

  const mode = cspMode();
  if (mode === "off") return NextResponse.next();

  const nonce = btoa(crypto.randomUUID());
  const policy = buildContentSecurityPolicy(nonce, process.env.NODE_ENV === "development", process.env.CSP_REPORT_URI || undefined);
  const header = mode === "report-only" ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy";

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set(header, policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set(header, policy);
  return response;
}

export const config = {
  matcher: [
    // Every page. Not the API (proxied to FastAPI, JSON only), build assets or public files.
    "/((?!api/|_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpe?g|webp|avif|gif|ico|txt|xml|webmanifest|woff2?|ttf|map)$).*)",
  ],
};
