import { expect, test } from "@playwright/test";
import { customerEmail, ids, loginCustomer } from "../test-helpers";

test("customer sees only their own enquiries and orders and cannot mutate order data", async ({ page }) => {
  test.setTimeout(75_000);
  await loginCustomer(page);
  await expect(page.getByRole("heading", { name: "Welcome, Synthetic Customer A" })).toBeVisible();
  await expect(page.getByText("Synthetic bottled water acceptance fixture").first()).toBeVisible();

  await page.goto("/account/enquiries");
  await expect(page.getByText("EB-RFQ-PW-FIXTURE-0001")).toBeVisible();
  await page.goto("/account/orders");
  await expect(page.getByText("EB-ORDER-PW-FIXTURE-0001")).toBeVisible();
  await expect(page.getByText("EB-ORDER-PW-FIXTURE-0002")).toHaveCount(0);
  await page.goto("/account/tracking");
  await expect(page.getByText("PW-TRACK-0001")).toBeVisible();
  await expect(page.getByText("Synthetic shipment departed origin")).toBeVisible();

  const base = process.env.PW_BASE_URL!;
  const foreignOrderStatus = await page.evaluate(async ({ url }) => {
    const response = await fetch(url, { credentials: "include" });
    return response.status;
  }, { url: `${base}/api/v1/customer/orders/${ids.orderBId}` });
  expect(foreignOrderStatus).toBe(404);
  const mutationStatus = await page.evaluate(async ({ url }) => {
    const response = await fetch(url, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "DELIVERED" }),
    });
    return response.status;
  }, { url: `${base}/api/v1/customer/orders/${ids.orderAId}` });
  expect(mutationStatus).toBe(405);

  const logoutResponse = page.waitForResponse((response) =>
    response.url().includes("/api/v1/customer/logout") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Log out" }).click();
  expect((await logoutResponse).ok()).toBe(true);
  const revoked = await page.evaluate(async () => {
    const response = await fetch("/api/v1/customer/me", { credentials: "include" });
    return response.status;
  });
  expect(revoked).toBe(401);
  expect(customerEmail).toContain("@example.com");
});
