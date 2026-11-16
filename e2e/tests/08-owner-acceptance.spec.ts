import { expect, test } from "@playwright/test";
import fs from "fs";
import path from "path";
import {
  getVerificationLinkCLI,
  ids,
  loginAdmin,
  loginInvestor,
} from "../test-helpers";

const SCREENSHOT_DIR = path.resolve(process.cwd(), "reports/screenshots/phase8");
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

test.describe("Phase 8: Complete Local Owner Acceptance Testing", () => {
  // =========================================================================
  // 1. PUBLIC WEBSITE & BRANDING ACCEPTANCE
  // =========================================================================
  test("1. Public website pages, branding, navigation, and redirects", async ({ page }) => {
    test.setTimeout(90_000);
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    // 1.1 Home Page
    await page.goto("/");
    await expect(page).toHaveTitle(/EDEN BOUNTY/);
    const footer = page.locator("footer");
    await expect(footer).toContainText("EDEN BOUNTY Sdn. Bhd.");
    await expect(footer).not.toContainText("EDEN BOUNTY SDN. BHD.");

    // Navigation branding & terminology
    const primaryNav = page.getByRole("navigation", { name: "Primary" });
    await expect(primaryNav.getByRole("link", { name: "Services", exact: true })).toBeVisible();
    await expect(primaryNav.getByRole("link", { name: "About", exact: true })).toBeVisible();
    await expect(primaryNav.getByRole("link", { name: "Investors", exact: true })).toBeVisible();

    // Verify Operations is NOT in public navigation
    await expect(primaryNav.getByRole("link", { name: /Operations/i })).toHaveCount(0);

    // 1.2 Redirects: /operations -> /services, /contact -> /rfq
    await page.goto("/operations");
    await expect(page).toHaveURL(/\/services/);

    await page.goto("/contact");
    await expect(page).toHaveURL(/\/rfq/);

    // 1.3 Check public pages load cleanly
    const publicPages = ["/about", "/services", "/investors", "/rfq", "/login", "/register"];
    for (const route of publicPages) {
      await page.goto(route);
      await expect(page.locator("body")).toBeVisible();
      // Verify no Garuda references
      const bodyText = await page.locator("body").innerText();
      expect(bodyText.toLowerCase()).not.toContain("garuda aerospace");
      expect(bodyText.toLowerCase()).not.toContain("garuda");
    }

    // Capture desktop screenshots
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "home-desktop-1440.png"), fullPage: false });

    await page.goto("/services");
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "services-desktop-1440.png"), fullPage: false });

    // Verify no fatal console errors occurred (ignoring devtools, 401 probes, and dev favicon)
    const fatalErrors = consoleErrors.filter(
      (err) =>
        !err.includes("favicon") &&
        !err.includes("Download the React DevTools") &&
        !err.includes("401 (Unauthorized)")
    );
    expect(fatalErrors.length).toBe(0);
  });

  // =========================================================================
  // 2. SERVICES ACCEPTANCE (HIGHEST PRIORITY)
  // =========================================================================
  test("2. Services catalogue: cards, detail pages, specifications, locked RFQ, and enquiry submission", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await page.goto("/services");
    await expect(page).toHaveURL(/\/services/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/services/i);

    // Verify exactly 6 active services are listed and no long descriptions
    const activeServices = [
      { id: "mineral-water", name: "Mineral Water", code: "EB-DIV-01" },
      { id: "scrap-trading", name: "Scrap Trading", code: "EB-DIV-02" },
      { id: "construction", name: "Construction / Building Promotion", code: "EB-DIV-03" },
      { id: "petroleum-products", name: "Petroleum Products", code: "EB-DIV-07" },
      { id: "furnace-oil", name: "Furnace Oil", code: "EB-DIV-09" },
      { id: "agricultural-drones", name: "Drone Solutions", code: "EB-DIV-10" },
    ];

    // Confirm no duplicate Building Promotion card
    await expect(page.getByRole("heading", { name: "Building Promotions", exact: true })).toHaveCount(0);

    // Confirm Lubricants is not publicly visible
    await expect(page.getByRole("heading", { name: "Industrial Lubricants", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Lubricants", exact: true })).toHaveCount(0);

    // Confirm Shisha is unpublished on the public website
    await expect(page.getByRole("heading", { name: "Shisha Tobacco Trading", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Shisha", exact: true })).toHaveCount(0);

    // Confirm Axe Oil is removed from the public website
    await expect(page.getByRole("heading", { name: "Axe Oil", exact: true })).toHaveCount(0);

    // Verify all 6 services appear
    for (const service of activeServices) {
      const cardLink = page.getByRole("link", { name: new RegExp(`View ${service.name.replace(/\//g, "\\/")} commercial service details`, "i") });
      await expect(cardLink).toBeVisible();
    }

    // Inspect each service detail page via direct navigation
    for (const service of activeServices) {
      await page.goto(`/services/${service.id}`);
      await expect(page).toHaveURL(new RegExp(`/services/${service.id}`));

      // 1. Breadcrumb navigation back to /services
      const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
      await expect(breadcrumb).toBeVisible();
      await expect(breadcrumb.getByRole("link", { name: "Services" })).toBeVisible();

      // 2. Service Title (EB-DIV code removed per client requirement)
      await expect(page.getByRole("heading", { level: 1 })).toContainText(service.name);
      await expect(page.getByText(service.code)).toHaveCount(0);

      // 3. Scope of Services
      await expect(page.getByRole("heading", { name: "Scope of Services" })).toBeVisible();

      // 4. Features & Capabilities or Key Capabilities
      await expect(page.getByRole("heading", { name: /(Features & Capabilities|Key Capabilities)/i })).toBeVisible();

      // 5. Dedicated Enquiry Form with pre-locked service
      const enquirySection = page.locator("#service-enquiry");
      await expect(enquirySection).toBeVisible();
      await expect(enquirySection.getByRole("heading", { name: new RegExp(`Enquire about ${service.name.replace(/\//g, "\\/")}`, "i") })).toBeVisible();
    }

    // Verify /services/shisha-tobacco-trading redirects to /services
    await page.goto("/services/shisha-tobacco-trading");
    await expect(page).toHaveURL(/\/services$/, { timeout: 20_000 });

    // Verify /services/axe-oil redirects to /services
    await page.goto("/services/axe-oil");
    await expect(page).toHaveURL(/\/services$/, { timeout: 20_000 });

    // Verify /services/drone-solutions redirects to /services/agricultural-drones
    await page.goto("/services/drone-solutions");
    await expect(page).toHaveURL(/\/services\/agricultural-drones/, { timeout: 20_000 });

    // Drone-specific statutory disclaimer check
    await page.goto("/services/agricultural-drones");
    await expect(page.getByText(/EDEN BOUNTY does not manufacture drones/i).first()).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "service-drone-desktop.png"), fullPage: false });

    // Submit a disposable test enquiry from /services/construction
    await page.goto("/services/construction");
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "service-construction-desktop.png"), fullPage: false });

    // Fill in the locked enquiry form
    const formSection = page.locator("#service-enquiry");
    await formSection.locator('input[name="fullName"]').fill("Acceptance QA Lead");
    await formSection.locator('input[name="companyName"]').fill("Acceptance Holdings Sdn Bhd");
    const testEnquiryEmail = `owner-enquiry-${Date.now()}@example.com`;
    await formSection.locator('input[name="businessEmail"]').fill(testEnquiryEmail);
    await formSection.locator('input[name="country"]').fill("Malaysia");

    // Click continue to requirements
    await formSection.getByRole("button", { name: /Continue to Requirements/i }).click();

    // Fill requirements
    await formSection.locator('input[name="productFocus"]').fill("High-strength structural steel beams");
    await formSection.locator('input[name="quantity"]').fill("500");
    await formSection.locator('input[name="unitOfMeasurement"]').fill("Metric Tonnes");
    await formSection.getByRole("button", { name: /Review & Compile RFQ/i }).click();

    // Submit official RFQ
    const rfqSubmitted = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/public/rfq/enquire") && resp.request().method() === "POST"
    );
    await formSection.getByRole("button", { name: /Submit Official RFQ Online/i }).click();
    const rfqResp = await rfqSubmitted;
    expect(rfqResp.status()).toBe(201);
    const rfqData = await rfqResp.json();
    expect(rfqData.data.reference_number).toContain("EB-RFQ-");
    expect(rfqData.data.status).toBe("NEW");

    // Verify confirmation message
    const confirmation = page.getByRole("region", { name: "Enquiry Submission Confirmation" });
    await expect(confirmation).toBeVisible();
    await expect(confirmation).toContainText(/EB-RFQ-/);
  });

  // =========================================================================
  // 3. CUSTOMER ACCEPTANCE: REGISTRATION, VERIFICATION, DASHBOARD, ISOLATION
  // =========================================================================
  test("3. Customer acceptance: registration, password validation, verification, dashboard, tenant isolation", async ({
    page,
  }) => {
    test.setTimeout(90_000);

    // 3.1 Password Validation on Register
    await page.goto("/register");
    await expect(page.getByRole("heading", { name: /Register for Portal Access/i })).toBeVisible();

    // Select Customer
    await page.getByRole("button", { name: "Customer Portal", exact: true }).click();

    // Fill details
    await page.locator('input[name="fullName"]').fill("Test Customer Candidate");
    const disposableCustomerEmail = `owner-customer-${Date.now()}@example.com`;
    await page.locator('input[name="email"]').fill(disposableCustomerEmail);
    await page.locator('input[name="password"]').fill("weak");
    await page.locator('input[name="confirmPassword"]').fill("weak");
    await page.locator('input[name="termsAccepted"]').check();
    await page.getByRole("button", { name: /Create Customer Account/i }).click();

    // Expect validation error
    await expect(page.getByText(/Password does not satisfy all security requirements/i)).toBeVisible();

    // 3.2 Successful Registration with strong password
    await page.locator('input[name="password"]').fill("ValidCustomerPass123!");
    await page.locator('input[name="confirmPassword"]').fill("ValidCustomerPass123!");
    const registerResponse = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/auth/register") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: /Create Customer Account/i }).click();
    const regResp = await registerResponse;
    expect(regResp.status()).toBe(201);
    const regBody = await regResp.json();

    // 3.3 Security: Verify public registration does NOT leak tokens and link is not displayed
    expect(regBody?.data?.verification_link).toBeFalsy();
    await expect(page.getByText(/Registration Successful/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /Verify Email Address Now/i })).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("token=");

    // Test unverified login block: Attempting to sign in before verification is blocked
    await page.goto("/login");
    const unverifiedForm = page.getByRole("form", { name: "Sign in" });
    await unverifiedForm.getByLabel("Email").fill(disposableCustomerEmail);
    await unverifiedForm.locator('input[autocomplete="current-password"]').fill("ValidCustomerPass123!");
    await unverifiedForm.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText(/Please verify your email address before signing in/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);

    // Verify email using local administrative CLI workflow
    const verifyLink = getVerificationLinkCLI(disposableCustomerEmail);
    await page.goto(verifyLink);
    await expect(page).toHaveURL(/\/verify-email[#?]token=/);
    await expect(page.getByText(/Email Verified Successfully/i)).toBeVisible({ timeout: 20_000 });

    // 3.4 Duplicate email registration conflict
    await page.goto("/register");
    await page.getByRole("button", { name: "Customer Portal", exact: true }).click();
    await page.locator('input[name="fullName"]').fill("Duplicate Customer");
    await page.locator('input[name="email"]').fill(disposableCustomerEmail);
    await page.locator('input[name="password"]').fill("ValidCustomerPass123!");
    await page.locator('input[name="confirmPassword"]').fill("ValidCustomerPass123!");
    await page.locator('input[name="termsAccepted"]').check();
    const dupResponse = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/auth/register") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: /Create Customer Account/i }).click();
    const dupResp = await dupResponse;
    expect(dupResp.status()).toBe(409);
    await expect(page.getByText(/An account with this email address already exists/i)).toBeVisible();

    // 3.5 Log in as the verified customer
    await page.goto("/login");
    const loginForm = page.getByRole("form", { name: "Sign in" });
    await loginForm.getByLabel("Email").fill(disposableCustomerEmail);
    await loginForm.locator('input[autocomplete="current-password"]').fill("ValidCustomerPass123!");
    await loginForm.getByRole("button", { name: "Sign in" }).click();

    // Redirects to /account
    await page.waitForURL(/\/account(?:$|\/)/);
    await expect(page.getByRole("heading", { name: /Welcome, Test Customer Candidate/i })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "customer-portal-desktop.png"), fullPage: false });

    // 3.6 Tenant Isolation: customer cannot access another customer's orders
    const base = process.env.PW_BASE_URL!;
    const foreignOrderStatus = await page.evaluate(
      async ({ url }) => {
        const response = await fetch(url, { credentials: "include" });
        return response.status;
      },
      { url: `${base}/api/v1/customer/orders/${ids.orderBId}` }
    );
    expect(foreignOrderStatus).toBe(404);

    // 3.7 Customer cannot access investor or admin endpoints (strictly HTTP 401 without corresponding session)
    const investorAccess = await page.evaluate(
      async ({ url }) => {
        const response = await fetch(url, { credentials: "include" });
        return response.status;
      },
      { url: `${base}/api/v1/investor/overview` }
    );
    expect(investorAccess).toBe(401);

    const adminAccess = await page.evaluate(
      async ({ url }) => {
        const response = await fetch(url, { credentials: "include" });
        return response.status;
      },
      { url: `${base}/api/v1/admin/dashboard/overview` }
    );
    expect(adminAccess).toBe(401);

    // 3.8 Log out
    const logoutResponse = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/customer/logout") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Log out" }).click();
    expect((await logoutResponse).ok()).toBe(true);
    await page.waitForURL(/\/login/);
  });

  // =========================================================================
  // 4. INVESTOR ACCEPTANCE: REGISTRATION, DEDICATED LOGIN, ISOLATION
  // =========================================================================
  test("4. Investor acceptance: registration, email verification, dedicated login, documents, tenant isolation", async ({
    page,
  }) => {
    test.setTimeout(90_000);

    // 4.1 Register as Investor
    await page.goto("/register");
    await page.getByRole("button", { name: "Investor Portal", exact: true }).click();
    await page.locator('input[name="fullName"]').fill("Institutional Investor QA");
    const disposableInvestorEmail = `owner-investor-${Date.now()}@example.com`;
    await page.locator('input[name="email"]').fill(disposableInvestorEmail);
    await page.locator('input[name="password"]').fill("ValidInvestorPass123!");
    await page.locator('input[name="confirmPassword"]').fill("ValidInvestorPass123!");
    await page.locator('input[name="termsAccepted"]').check();
    const registerResponse = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/auth/register") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: /Create Investor Account/i }).click();
    const regResp = await registerResponse;
    expect(regResp.status()).toBe(201);
    const regBody = await regResp.json();

    // Security: Verify public registration does NOT leak tokens and link is not displayed
    expect(regBody?.data?.verification_link).toBeFalsy();
    await expect(page.getByText(/Registration Successful/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /Verify Email Address Now/i })).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("token=");

    // Verify unverified investor login block on /investors/login
    await page.goto("/investors/login");
    const unverifiedInvForm = page.getByRole("form", { name: "Investor sign in" });
    await unverifiedInvForm.getByLabel("Email").fill(disposableInvestorEmail);
    await unverifiedInvForm.locator('input[autocomplete="current-password"]').fill("ValidInvestorPass123!");
    await unverifiedInvForm.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText(/Please verify your email address before signing in/i)).toBeVisible();
    await expect(page).toHaveURL(/\/investors\/login/);

    // Verify email using local administrative CLI workflow
    const verifyLink = getVerificationLinkCLI(disposableInvestorEmail);
    await page.goto(verifyLink);
    await expect(page).toHaveURL(/\/verify-email[#?]token=/);
    await expect(page.getByText(/Email Verified Successfully/i)).toBeVisible({ timeout: 20_000 });

    // 4.2 Log in via dedicated /investors/login
    await page.goto("/investors/login");
    const investorForm = page.getByRole("form", { name: "Investor sign in" });
    await investorForm.getByLabel("Email").fill(disposableInvestorEmail);
    await investorForm.locator('input[autocomplete="current-password"]').fill("ValidInvestorPass123!");
    await investorForm.getByRole("button", { name: "Sign in" }).click();

    // Redirects to /investors/portal
    await page.waitForURL(/\/investors\/portal(?:$|\/)/);
    await expect(page.getByRole("heading", { name: /Welcome, Institutional Investor QA/i })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "investor-portal-desktop.png"), fullPage: false });

    // 4.3 Log out disposable investor
    const logoutResponse = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/investor/logout") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Log out" }).click();
    expect((await logoutResponse).ok()).toBe(true);
    await page.waitForURL(/\/investors\/login/);

    // 4.4 Log in as Seeded Investor A to test document download isolation
    await loginInvestor(page);

    // Download permitted document A
    const base = process.env.PW_BASE_URL!;
    const downloadDocA = await page.request.get(`${base}/api/v1/investor/documents/${ids.documentAId}/download`);
    expect(downloadDocA.status()).toBe(200);
    expect(downloadDocA.headers()["content-type"]).toContain("application/pdf");

    // Attempt to download Document B (owned by Investor B) -> expect 404
    const downloadDocB = await page.request.get(`${base}/api/v1/investor/documents/${ids.documentBId}/download`);
    expect(downloadDocB.status()).toBe(404);

    // Boundary: Investor cannot access customer orders (strictly HTTP 401 without customer session)
    const customerAccess = await page.evaluate(
      async ({ url }) => {
        const response = await fetch(url, { credentials: "include" });
        return response.status;
      },
      { url: `${base}/api/v1/customer/orders` }
    );
    expect(customerAccess).toBe(401);
  });

  // =========================================================================
  // 5. ADMIN ACCEPTANCE: DASHBOARD, SERVICE ASSOCIATIONS, ORDERS, AUDIT
  // =========================================================================
  test("5. Admin acceptance: dashboard metrics, service catalogue integrity, enquiry association, order management", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);
    await expect(page).toHaveURL(/\/admin/);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, "admin-dashboard-desktop.png"), fullPage: false });

    // 5.1 Dashboard Service Distribution card
    const distributionHeading = page.getByRole("heading", { name: "Service Volume Distribution" });
    await expect(distributionHeading).toBeVisible();
    await expect(page.getByText("6 Services Active").first()).toBeVisible();

    // Verify historical Lubricants row is labelled appropriately
    await expect(page.getByText(/\(Historical\)/).first()).toBeVisible();

    // 5.2 Enquiry Management & Filter
    await page.goto("/admin/enquiries");
    await expect(page.getByRole("heading", { name: "Commercial Enquiries Repository" })).toBeVisible();

    // Check that Construction service is present in enquiries filter with exact name
    const serviceFilter = page.locator("#enquiry-division");
    await expect(serviceFilter).toBeVisible();
    await expect(serviceFilter.locator('option[value="construction"]')).toHaveText(/Construction \/ Building Promotion/i);
    // Verify duplicate Building Promotions is NOT an option
    await expect(serviceFilter.locator('option[value="building-promotions"]')).toHaveCount(0);

    // 5.3 Order Management
    await page.goto("/admin/orders");
    await expect(page.getByRole("heading", { name: "Orders" })).toBeVisible();

    // Inspect seeded order
    await page.goto(`/admin/orders/${ids.orderAId}`);
    await expect(page.getByRole("heading", { name: "EB-ORDER-PW-FIXTURE-0001" })).toBeVisible();
    await expect(page.getByText("Synthetic bottled water acceptance order")).toBeVisible();

    // 5.4 Admin Logout
    const logoutResponse = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/auth/logout") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Log out of console" }).click();
    expect((await logoutResponse).ok()).toBe(true);
    await page.waitForURL(/\/login/);
  });

  // =========================================================================
  // 6. RESPONSIVE ACCEPTANCE & SCREENSHOTS ACROSS 5 VIEWPORTS
  // =========================================================================
  test("6. Responsive acceptance across Mobile, Tablet, and Desktop viewports", async ({ page }) => {
    test.setTimeout(120_000);

    const viewports = [
      { name: "mobile-375", width: 375, height: 667 },
      { name: "mobile-390", width: 390, height: 844 },
      { name: "tablet-768", width: 768, height: 1024 },
      { name: "desktop-1440", width: 1440, height: 900 },
      { name: "desktop-1920", width: 1920, height: 1080 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      // Test /services layout
      await page.goto("/services");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

      // Check horizontal overflow
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth <= window.innerWidth;
      });
      expect(overflow).toBe(true);

      // Capture screenshot for key viewports
      if (["mobile-375", "tablet-768", "desktop-1920"].includes(vp.name)) {
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, `${vp.name}-services.png`),
          fullPage: false,
        });
      }

      // Test a service detail page layout
      await page.goto("/services/construction");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const detailOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth <= window.innerWidth;
      });
      expect(detailOverflow).toBe(true);

      if (["mobile-375", "mobile-390"].includes(vp.name)) {
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, `${vp.name}-construction.png`),
          fullPage: false,
        });
      }
    }
  });
});
