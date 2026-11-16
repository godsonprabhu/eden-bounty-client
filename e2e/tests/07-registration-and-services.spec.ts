import { expect, test } from "@playwright/test";
import {
  adminEmail,
  customerBEmail,
  getVerificationLinkCLI,
  ids,
  loginCustomer,
  loginInvestor,
  testPassword,
} from "../test-helpers";

test.describe("Phase 6: Client Changes, Services Redesign, and Registration Acceptance", () => {
  // Test 1: Terminology & Company Name
  test("1. Terminology is 'Services' and company name is 'EDEN BOUNTY Sdn. Bhd.'", async ({ page }) => {
    await page.goto("/");
    const footerText = await page.locator("footer").innerText();
    expect(footerText).toContain("EDEN BOUNTY Sdn. Bhd.");
    expect(footerText).not.toContain("EDEN BOUNTY SDN. BHD.");

    const primaryNav = page.getByRole("navigation", { name: "Primary" });
    await expect(primaryNav.getByRole("link", { name: "Services", exact: true })).toBeVisible();
    await expect(page.getByText(/all services/i).first()).toBeVisible();
  });

  // Test 2 (Requirement 9): Main Services page displaying cards without long descriptions
  test("2. Main Services page (/services) displays responsive card grid without long descriptions", async ({ page }) => {
    await page.goto("/services");
    await expect(page).toHaveURL(/\/services/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/services/i);

    // Active division cards are present (all 6 approved public services)
    await expect(page.getByRole("heading", { name: "Mineral Water" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Scrap Trading" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Construction / Building Promotion" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Petroleum Products" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Furnace Oil" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Drone Solutions" }).first()).toBeVisible();

    // Confirm withdrawn services, duplicate cards, and internal identifiers are NOT visible publicly
    await expect(page.getByRole("heading", { name: "Building Promotions", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /Industrial Lubricants|Lubricants/i })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /Shisha/i })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /Axe Oil/i })).toHaveCount(0);
    await expect(page.getByText(/EB-DIV-\d{2}/)).toHaveCount(0);

    // Verify cards do NOT display long narrative descriptions or full spec lists on main listing
    const mineralWaterCard = page.getByRole("link", { name: /View Mineral Water commercial service details/i });
    await expect(mineralWaterCard).toBeVisible();
    await expect(mineralWaterCard).toHaveAttribute("href", "/services/mineral-water");

    // The old heavy feature section has been removed from /services
    await expect(page.locator("#agritech")).toHaveCount(0);
  });

  // Test 3 (Requirement 10): Clicking each service card opens the correct detail page & alias redirect
  test("3. Clicking service card navigates to /services/[slug] and alias redirects", async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto("/services");
    const mineralWaterCard = page.getByRole("link", { name: /View Mineral Water commercial service details/i });
    await mineralWaterCard.click();
    await expect(page).toHaveURL(/\/services\/mineral-water/, { timeout: 20_000 });

    // Breadcrumb navigation back to /services
    const breadcrumbServicesLink = page
      .getByRole("navigation", { name: "Breadcrumb" })
      .getByRole("link", { name: "Services" });
    await expect(breadcrumbServicesLink).toBeVisible();
    await breadcrumbServicesLink.click();
    await expect(page).toHaveURL(/\/services/, { timeout: 20_000 });

    // Verify /services/robotics alias redirects to /services/agricultural-drones
    await page.goto("/services/robotics");
    await expect(page).toHaveURL(/\/services\/agricultural-drones/, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Drone Solutions");

    // Verify /services/building-promotions redirects to canonical /services/construction
    await page.goto("/services/building-promotions");
    await expect(page).toHaveURL(/\/services\/construction/, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Construction / Building Promotion");

    // Verify /services/lubricants redirects back to /services (withdrawn from public site)
    await page.goto("/services/lubricants");
    await expect(page).toHaveURL(/\/services$/, { timeout: 20_000 });

    // Verify /services/axe-oil redirects back to /services (withdrawn from public site)
    await page.goto("/services/axe-oil");
    await expect(page).toHaveURL(/\/services$/, { timeout: 20_000 });

    // Verify /services/shisha-tobacco-trading redirects back to /services (withdrawn from public site)
    await page.goto("/services/shisha-tobacco-trading");
    await expect(page).toHaveURL(/\/services$/, { timeout: 20_000 });
  });

  // Test 4 (Requirement 11): Service detail page displays all 8 items
  test("4. Service detail page displays all 8 required items", async ({ page }) => {
    await page.goto("/services/mineral-water");

    // Item 1: Service title (EB-DIV code removed per client requirement)
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Mineral Water");
    await expect(page.getByText("EB-DIV-01")).toHaveCount(0);

    // Item 2: Large relevant service image
    const heroImage = page.locator("img[alt*='Mineral Water']");
    await expect(heroImage).toBeVisible();

    // Item 3: Detailed service description
    await expect(page.getByText(/Clean, safe drinking water from a protected source/i)).toBeVisible();

    // Item 4: Scope of services
    await expect(page.getByRole("heading", { name: "Scope of Services" })).toBeVisible();

    // Item 5: Features and capabilities
    await expect(page.getByRole("heading", { name: "Features & Capabilities" })).toBeVisible();

    // Item 6: Relevant technical specifications
    await expect(page.getByRole("heading", { name: "Technical Specifications" })).toBeVisible();
    await expect(page.getByText("pH Range")).toBeVisible();

    // Item 7: Applications and use cases
    await expect(page.getByRole("heading", { name: "Applications & Use Cases" })).toBeVisible();

    // Item 8: Service-specific locked enquiry form
    const enquirySection = page.locator("#service-enquiry");
    await expect(enquirySection).toBeVisible();
    await expect(enquirySection.getByRole("heading", { name: /Enquire about Mineral Water/i })).toBeVisible();
  });

  // Test 5 (Requirement 12): Service-specific enquiry submission (verifying service lock)
  test("5. Service-specific enquiry form enforces lock and submits RFQ", async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto("/services/mineral-water");
    const enquirySection = page.locator("#service-enquiry");

    // Stage 1 is locked; form starts on Stage 2 (Contact) with Mineral Water pre-locked
    await enquirySection.locator('input[name="fullName"]').fill("Test Procurement Buyer");
    await enquirySection.locator('input[name="companyName"]').fill("Acme Water Distributors Sdn Bhd");
    await enquirySection.locator('input[name="businessEmail"]').fill(`mw-rfq-${Date.now()}@example.com`);
    await enquirySection.locator('input[name="country"]').fill("Malaysia");
    await enquirySection.getByRole("button", { name: /Continue to Requirements/i }).click();

    // Stage 3: Requirements
    await enquirySection.locator('input[name="productFocus"]').fill("Natural mineral water 500ml export cases");
    await enquirySection.getByRole("button", { name: /Review & Compile RFQ/i }).click();

    // Stage 4: Review confirms pre-selected service and submit
    await expect(enquirySection.getByText("Mineral Water", { exact: false }).first()).toBeVisible();
    await expect(enquirySection.getByText("Pre-selected")).toBeVisible();

    // Submit online RFQ
    await enquirySection.getByRole("button", { name: /Submit Official RFQ Online/i }).click();
    await expect(enquirySection.getByRole("heading", { name: /Trade Enquiry Confirmed/i })).toBeVisible({
      timeout: 15_000,
    });
    await expect(enquirySection.getByText(/EB-RFQ-/i).first()).toBeVisible();
  });

  // Test 6 (Requirements 1, 3, 4, 5): Customer registration, unverified block, verification, login to /account
  test("6. Customer registration, unverified login block, email verification, and login to /account", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const suffix = `${Date.now()}_${Math.floor(Math.random() * 10000)}`;
    const email = `newcust-${suffix}@example.com`;
    const password = "Valid-Password-123!";

    // 1. Visit /register?role=customer
    await page.goto("/register?role=customer");
    await expect(page.getByRole("heading", { name: /Register for Portal Access/i })).toBeVisible();

    // 2. Fill registration form
    await page.locator('input[name="fullName"]').fill("New Test Customer");
    await page.locator('input[name="email"]').fill(email);
    await page.locator('input[name="companyName"]').fill("New Enterprise Sdn Bhd");
    await page.locator('input[name="password"]').fill(password);
    await page.locator('input[name="confirmPassword"]').fill(password);
    await page.locator('input[name="termsAccepted"]').check();

    const registerPromise = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/auth/register") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: /Create Customer Account/i }).click();
    const regResp = await registerPromise;
    expect(regResp.status()).toBe(201);
    const regBody = await regResp.json();

    // 3. Security: Verify public registration response NEVER discloses verification tokens or links
    expect(regBody?.data?.verification_link).toBeFalsy();
    expect(regBody?.data).not.toHaveProperty("token");
    expect(JSON.stringify(regBody)).not.toContain("token=");

    // Verify UI confirms registration without displaying verification links or secret tokens
    await expect(page.getByText(/Registration Successful/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /Verify Email Address Now/i })).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("token=");

    // 4. Test unverified login block: Attempting to sign in before verification is rejected
    await page.goto("/login");
    await page.locator('input[name="email"]').fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: /Sign in/i }).click();
    await expect(page.getByText(/Please verify your email address before signing in/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);

    // 5. Complete email verification using controlled local administrative CLI workflow
    const verifyLink = getVerificationLinkCLI(email);
    expect(verifyLink).toContain("/verify-email#token=");

    // Visiting the single-use verification link verifies the email address
    await page.goto(verifyLink);
    await expect(page.getByText(/Email Verified Successfully/i)).toBeVisible({ timeout: 20_000 });

    // 6. Sign in with verified credentials -> Successfully lands on /account
    await page.goto("/login");
    await page.locator('input[name="email"]').fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: /Sign in/i }).click();
    await expect(page).toHaveURL(/\/account/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Welcome, New Test Customer/i);
  });

  // Test 7 (Requirements 2, 3, 6): Investor registration, email verification, and login to /investors/portal
  test("7. Investor registration, email verification, and login to /investors/portal", async ({ page }) => {
    test.setTimeout(90_000);
    const suffix = `${Date.now()}_${Math.floor(Math.random() * 10000)}`;
    const email = `newinvestor-${suffix}@example.com`;
    const password = "Investor-Password-99!";

    // 1. Visit /register?role=investor
    await page.goto("/register?role=investor");
    await expect(page.getByRole("heading", { name: /Register for Portal Access/i })).toBeVisible();

    // 2. Fill registration form
    await page.locator('input[name="fullName"]').fill("New Test Investor");
    await page.locator('input[name="email"]').fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.locator('input[name="confirmPassword"]').fill(password);
    await page.locator('input[name="termsAccepted"]').check();

    const registerPromise = page.waitForResponse(
      (resp) => resp.url().includes("/api/v1/auth/register") && resp.request().method() === "POST"
    );
    await page.getByRole("button", { name: /Create Investor Account/i }).click();
    const regResp = await registerPromise;
    expect(regResp.status()).toBe(201);
    const regBody = await regResp.json();

    // 3. Security: Verify public registration response NEVER discloses verification tokens or links
    expect(regBody?.data?.verification_link).toBeFalsy();
    expect(regBody?.data).not.toHaveProperty("token");
    expect(JSON.stringify(regBody)).not.toContain("token=");

    // Verify UI confirms registration without displaying verification links or secret tokens
    await expect(page.getByText(/Registration Successful/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /Verify Email Address Now/i })).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("token=");

    // 4. Test unverified investor login block on dedicated investor login
    await page.goto("/investors/login");
    await page.locator('input[name="email"]').fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: /Sign in/i }).click();
    await expect(page.getByText(/Please verify your email address before signing in/i)).toBeVisible();
    await expect(page).toHaveURL(/\/investors\/login/);

    // 5. Complete verification using controlled local administrative CLI workflow
    const verifyLink = getVerificationLinkCLI(email);
    expect(verifyLink).toContain("/verify-email#token=");

    await page.goto(verifyLink);
    await expect(page.getByText(/Email Verified Successfully/i)).toBeVisible({ timeout: 20_000 });

    // 6. Sign in on investor portal login -> Successfully lands on /investors/portal
    await page.goto("/investors/login");
    await page.locator('input[name="email"]').fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: /Sign in/i }).click();
    await expect(page).toHaveURL(/\/investors\/portal/, { timeout: 30_000 });
  });

  // Test 8 (Requirement 7): Admin login at /login -> /admin and prohibit public admin registration
  test("8. Admin login at /login redirects to /admin and public registration prohibits admin creation", async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);
    await page.goto("/login");
    const form = page.getByRole("form", { name: "Sign in" });
    await form.getByLabel("Email").fill(adminEmail);
    await form.locator('input[autocomplete="current-password"]').fill(testPassword);
    await form.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/admin(?:$|\/)/, { timeout: 30_000 });
    await expect(page.getByText(/Central Administrative Console/i).or(page.getByText(/Super Admin/i)).first()).toBeVisible();

    // Prohibit public admin registration via API: exactly HTTP 422 Unprocessable Entity
    const adminRegResponse = await request.post("/api/v1/auth/register", {
      data: {
        email: `hacked-admin-${Date.now()}@example.com`,
        password: "Admin-Hacked-123!",
        full_name: "Illegal Admin Attempter",
        role: "ADMIN",
        terms_accepted: true,
      },
    });
    expect(adminRegResponse.status()).toBe(422);

    const superAdminRegResponse = await request.post("/api/v1/auth/register", {
      data: {
        email: `hacked-super-${Date.now()}@example.com`,
        password: "Admin-Hacked-123!",
        full_name: "Illegal Super Admin Attempter",
        role: "SUPER_ADMIN",
        terms_accepted: true,
      },
    });
    expect(superAdminRegResponse.status()).toBe(422);
  });

  // Test 9 (Requirement 8): Customer & Investor data isolation
  test("9. Customer and Investor data isolation prevents cross-tenant access", async ({ browser }) => {
    test.setTimeout(75_000);
    const base = process.env.PW_BASE_URL!;

    // 1. Customer Context (use customerBEmail since customerA password was reset in test 05)
    const customerContext = await browser.newContext();
    const customerPage = await customerContext.newPage();
    await loginCustomer(customerPage, customerBEmail);
    await expect(customerPage).toHaveURL(/\/account/);

    // Customer cannot access Investor endpoints (strictly HTTP 401 without investor session)
    const customerAccessInvestor = await customerPage.evaluate(
      async ({ url }) => {
        const res = await fetch(url, { credentials: "include" });
        return res.status;
      },
      { url: `${base}/api/v1/investor/me` }
    );
    expect(customerAccessInvestor).toBe(401);

    // Customer cannot access another customer's order (strictly HTTP 404 per isolation contract)
    const customerAccessOrderA = await customerPage.evaluate(
      async ({ url }) => {
        const res = await fetch(url, { credentials: "include" });
        return res.status;
      },
      { url: `${base}/api/v1/customer/orders/${ids.orderAId}` }
    );
    expect(customerAccessOrderA).toBe(404);

    // 2. Investor Context (clean isolated session, no customer cookies)
    const investorContext = await browser.newContext();
    const investorPage = await investorContext.newPage();
    await loginInvestor(investorPage);
    await expect(investorPage).toHaveURL(/\/investors\/portal/);

    // Investor cannot access Customer endpoints (strictly HTTP 401 without customer session)
    const investorAccessCustomer = await investorPage.evaluate(
      async ({ url }) => {
        const res = await fetch(url, { credentials: "include" });
        return res.status;
      },
      { url: `${base}/api/v1/customer/me` }
    );
    expect(investorAccessCustomer).toBe(401);

    // Investor cannot access another investor's private document download (strictly HTTP 404)
    const investorAccessDocB = await investorPage.request.get(
      `${base}/api/v1/investor/documents/${ids.documentBId}/download`
    );
    expect(investorAccessDocB.status()).toBe(404);

    await customerContext.close();
    await investorContext.close();
  });

  // Test 10: Google OAuth endpoint structure check
  test("10. Google OAuth endpoint returns configured=false when unconfigured and rejects invalid roles", async ({ request }) => {
    // 1. Unconfigured state returns configured=false without requiring real Google credentials
    const response = await request.get("/api/v1/auth/google/url?role=CUSTOMER");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.configured).toBe(false);
    expect(data.url).toBeNull();
    expect(data.state).toBeNull();
    expect(data.message).toContain("Google OAuth 2.0 is not configured on this server");

    // Also verify for INVESTOR role
    const invResponse = await request.get("/api/v1/auth/google/url?role=INVESTOR");
    expect(invResponse.status()).toBe(200);
    const invData = await invResponse.json();
    expect(invData.configured).toBe(false);
    expect(invData.url).toBeNull();

    // 2. Rejects invalid administrative roles with HTTP 400
    const invalidRoleResponse = await request.get("/api/v1/auth/google/url?role=ADMIN");
    expect(invalidRoleResponse.status()).toBe(400);
    const adminErr = await invalidRoleResponse.json();
    expect(adminErr.detail).toContain("Google sign-in is only available for customer and investor accounts");

    const superAdminResponse = await request.get("/api/v1/auth/google/url?role=SUPER_ADMIN");
    expect(superAdminResponse.status()).toBe(400);
  });
});
