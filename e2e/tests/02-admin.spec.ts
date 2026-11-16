import { expect, test } from "@playwright/test";
import { ids, loginAdmin } from "../test-helpers";

test("admin reviews a seeded enquiry, converts it to an order, and logs out", async ({ page }) => {
  test.setTimeout(80_000);
  await loginAdmin(page);
  await expect(page.getByRole("link", { name: "Enquiries" })).toBeVisible();

  await page.goto(`/admin/enquiries/${ids.enquiryId}`);
  await expect(page.getByText("Synthetic bottled water acceptance fixture").first()).toBeVisible();
  await page.getByLabel("Internal operational note content").fill("Synthetic Playwright review note");
  await page.getByRole("button", { name: "Add Note" }).click();
  await expect(page.getByText("Internal note appended successfully")).toBeVisible();

  await page.getByRole("button", { name: "Convert to order" }).click();
  await expect(page.getByRole("dialog", { name: /Convert EB-RFQ-PW-FIXTURE-0001 to an order/ })).toBeVisible();
  await page.getByRole("button", { name: "Create order" }).click();
  const createdToast = page.getByText(/Order EB-ORD-/);
  await expect(createdToast).toBeVisible();
  expect((await createdToast.innerText()).match(/EB-ORD-[A-Z0-9-]+/)?.[0]).toBeTruthy();

  const logoutResponse = page.waitForResponse((response) =>
    response.url().includes("/api/v1/auth/logout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Log out of console" }).click();
  expect((await logoutResponse).ok()).toBe(true);
  await page.waitForURL(/\/login/);
  const revoked = await page.request.get(`${process.env.PW_BASE_URL}/api/v1/auth/me`);
  expect(revoked.status()).toBe(401);
});

test("admin updates an order status, shipment and audit history", async ({ page }) => {
  test.setTimeout(60_000);
  await loginAdmin(page);
  await page.goto(`/admin/orders/${ids.orderAId}`);
  await expect(page.getByRole("heading", { name: "EB-ORDER-PW-FIXTURE-0001" })).toBeVisible();

  await page.getByRole("button", { name: "Update status" }).click();
  await page.getByLabel("New status").selectOption({ label: "Delivered" });
  await page.getByLabel("Note to customer").fill("Synthetic Playwright order status update");
  await page.getByRole("button", { name: "Update status" }).last().click();
  await expect(page.getByText("Order status updated.")).toBeVisible();

  await page.getByRole("button", { name: "Add shipment" }).click();
  await page.getByLabel("Carrier").fill("Synthetic Playwright Carrier");
  await page.getByLabel("Tracking number").fill("PW-NEW-TRACK-01");
  await page.getByRole("textbox", { name: "From" }).fill("Port Klang");
  await page.getByRole("textbox", { name: "To" }).fill("Synthetic Test Port");
  await page.getByRole("button", { name: "Add shipment" }).last().click();
  await expect(page.getByText("PW-NEW-TRACK-01")).toBeVisible();

  await page.getByRole("button", { name: "Add tracking update" }).last().click();
  await page.getByRole("textbox", { name: "Update *" }).fill("Synthetic shipment accepted at origin");
  await page.getByLabel("Location").fill("Port Klang");
  await page.getByRole("button", { name: "Add update" }).click();
  await expect(page.getByText("Synthetic shipment accepted at origin")).toBeVisible();

  await page.goto("/admin/audit");
  await expect(page.getByRole("heading", { name: "Admin Audit Ledger" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "ORDER_STATUS_UPDATED", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Log out of console" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("admin creates a customer and the customer accepts a single-use invitation", async ({ page }) => {
  test.setTimeout(60_000);
  await loginAdmin(page);
  await page.goto("/admin/customers");
  await page.getByRole("button", { name: "New customer" }).click();
  await page.getByLabel("Full name").fill("Synthetic Invited Customer");
  await page.getByLabel("Sign-in email").fill(process.env.PW_NEW_CUSTOMER_EMAIL!);
  await page.getByLabel("Company").fill("Synthetic Invitation Company");
  await page.getByLabel("Country").fill("Malaysia");
  await page.getByRole("button", { name: "Create account" }).click();

  const invitation = page.getByRole("textbox", { name: "invitation link" });
  await expect(invitation).toBeVisible();
  const inviteUrl = await invitation.inputValue();
  expect(inviteUrl).toContain("/reset-password#token=");
  await page.goto(inviteUrl);
  await page.getByLabel("New password", { exact: true }).fill(process.env.PW_TEST_PASSWORD!);
  await page.getByLabel("Confirm password", { exact: true }).fill(process.env.PW_TEST_PASSWORD!);
  await page.getByRole("button", { name: "Save password" }).click();
  await expect(page.getByText(/password has been saved/i)).toBeVisible();
});

test("admin order management and audit screens are protected until sign-in", async ({ page }) => {
  await page.goto("/admin/orders");
  await expect(page).toHaveURL(/\/login/);
  await loginAdmin(page);
  await page.goto("/admin/orders");
  await expect(page.getByRole("heading", { name: "Orders" })).toBeVisible();
  await expect(page.getByText("EB-ORDER-PW-FIXTURE-0001")).toBeVisible();
});
