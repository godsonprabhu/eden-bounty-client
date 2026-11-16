import { expect, test } from "@playwright/test";

const PUBLIC_ROUTES = [
  { path: "/", title: /EDEN BOUNTY/ },
  { path: "/about", title: /About|EDEN BOUNTY/ },
  { path: "/services", title: /Services|EDEN BOUNTY/ },
  { path: "/rfq", title: /RFQ|Enquiry|EDEN BOUNTY/ },
  { path: "/login", title: /Sign In|Login|EDEN BOUNTY/ },
  { path: "/investors/login", title: /Investor|Sign In|EDEN BOUNTY/ },
  { path: "/forgot-password", title: /Reset|Forgot|EDEN BOUNTY/ },
];

const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
];

test.describe("Phase 5: Production Acceptance - Public Pages and Console Hygiene", () => {
  for (const route of PUBLIC_ROUTES) {
    test(`public page ${route.path} loads cleanly without console errors`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(msg.text());
        }
      });
      page.on("pageerror", (err) => {
        consoleErrors.push(err.message);
      });

      const response = await page.goto(route.path, { waitUntil: "domcontentloaded" });
      expect(response?.status()).toBe(200);
      await expect(page).toHaveTitle(route.title);
      expect(consoleErrors).toEqual([]);
    });
  }
});

test.describe("Phase 5: Production Acceptance - Responsive Layouts (No Horizontal Overflow)", () => {
  for (const vp of VIEWPORTS) {
    for (const route of ["/", "/about", "/services", "/rfq", "/login"]) {
      test(`${route} responsive layout on ${vp.name} (${vp.width}x${vp.height}) has no horizontal overflow`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(route, { waitUntil: "domcontentloaded" });

        const dimensions = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          innerWidth: window.innerWidth,
        }));

        expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.innerWidth);
      });
    }
  }
});

test.describe("Phase 5: Production Acceptance - Protected Route Gates (Defense in Depth)", () => {
  test("unauthenticated admin routes redirect to sign-in with returnUrl", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login\?returnUrl=%2Fadmin/);

    await page.goto("/admin/audit");
    await expect(page).toHaveURL(/\/login\?returnUrl=%2Fadmin%2Faudit/);

    await page.goto("/admin/orders");
    await expect(page).toHaveURL(/\/login\?returnUrl=%2Fadmin%2Forders/);
  });

  test("unauthenticated customer portal routes redirect to sign-in", async ({ page }) => {
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/account/orders");
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/account/enquiries");
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated investor portal routes redirect to investor sign-in", async ({ page }) => {
    await page.goto("/investors/portal");
    await expect(page).toHaveURL(/\/investors\/login/);

    await page.goto("/investors/portal/documents");
    await expect(page).toHaveURL(/\/investors\/login/);
  });
});

test.describe("Phase 5: Production Acceptance - Security Headers", () => {
  test("standard pages carry baseline security headers and dynamic CSP nonce", async ({ page }) => {
    const response = await page.goto("/");
    expect(response).not.toBeNull();
    const headers = response!.headers();

    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["referrer-policy"]).toContain("strict-origin");

    const csp = headers["content-security-policy"];
    expect(csp).toBeTruthy();
    expect(csp).toContain("default-src 'self'");
    expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  });

  test("authentication pages enforce no-referrer policy", async ({ page }) => {
    const response = await page.goto("/login");
    expect(response).not.toBeNull();
    const headers = response!.headers();

    expect(headers["referrer-policy"]).toBe("no-referrer");
  });
});
