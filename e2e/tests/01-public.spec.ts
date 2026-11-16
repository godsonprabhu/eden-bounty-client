import { expect, test } from "@playwright/test";

test("public navigation and active divisions render", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");
  await expect(page).toHaveTitle(/EDEN BOUNTY/);
  const primaryNavigation = page.getByRole("navigation", { name: "Primary" });
  const servicesLink = primaryNavigation.getByRole("link", { name: "Services", exact: true });
  await servicesLink.click();
  await expect(page).toHaveURL(/\/services/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: /Mineral Water/ }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /Scrap Trading/ }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Enquire/ }).first()).toHaveAttribute("href", /\/rfq\?division=/);
});

test("about and services pages are reachable from the public navigation", async ({ page }) => {
  await page.goto("/");
  const primaryNavigation = page.getByRole("navigation", { name: "Primary" });
  await primaryNavigation.getByRole("link", { name: "About", exact: true }).click();
  await expect(page).toHaveURL(/\/about/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/services");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/all services/i).first()).toBeVisible();
});

test("RFQ enforces required fields and submits synthetic data", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/rfq");
  const nextContact = page.getByRole("button", { name: /Continue to Contact Details/ });
  await expect(nextContact).toBeDisabled();
  await page.getByRole("radio", { name: /Mineral Water/ }).click();
  await nextContact.click();
  await page.getByRole("button", { name: /Continue to Requirements/ }).click();
  await expect(page.getByRole("alert").getByRole("button", { name: "Contact person full name is required." })).toBeVisible();

  await page.locator('input[name="fullName"]').fill("Synthetic Browser Contact");
  await page.locator('input[name="companyName"]').fill("Synthetic Browser Buyer");
  await page.locator('input[name="businessEmail"]').fill(`rfq-${Date.now()}@example.com`);
  await page.locator('input[name="country"]').fill("Malaysia");
  await page.getByRole("button", { name: /Continue to Requirements/ }).click();
  await page.locator('input[name="productFocus"]').fill("Synthetic acceptance bottled water");
  await page.getByRole("button", { name: /Review & Compile RFQ/ }).click();
  await expect(page.getByRole("button", { name: /Submit Official RFQ Online/ })).toBeVisible();

  const submitted = page.waitForResponse((response) =>
    response.url().includes("/api/v1/public/rfq/enquire") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Submit Official RFQ Online/ }).click();
  const response = await submitted;
  expect(response.status()).toBe(201);
  const confirmation = page.getByRole("region", { name: "Enquiry Submission Confirmation" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toContainText(/EB-RFQ-/);
});

test("services layout does not overflow a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/services");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const widths = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
});
