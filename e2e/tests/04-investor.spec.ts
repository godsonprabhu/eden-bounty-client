import { expect, test } from "@playwright/test";
import { ids, loginInvestor } from "../test-helpers";

test("investor sees their overview, history and approved updates", async ({ page }) => {
  test.setTimeout(75_000);
  await loginInvestor(page);
  await expect(page.getByRole("heading", { name: "Welcome, Synthetic Investor A" })).toBeVisible();
  await expect(page.getByText("MYR 50,000.00", { exact: true }).first()).toBeVisible();

  await page.goto("/investors/portal/investments");
  await expect(page.getByText("EB-INV-PW-0001")).toBeVisible();
  await page.goto("/investors/portal/updates");
  await expect(page.getByText("Synthetic public investor update")).toBeVisible();
  await expect(page.getByText("Synthetic private investor B update")).toHaveCount(0);

});

test("investor document downloads are restricted to the signed-in owner", async ({ page }) => {
  await loginInvestor(page);
  const download = await page.request.get(`${process.env.PW_BASE_URL}/api/v1/investor/documents/${ids.documentAId}/download`);
  expect(download.status()).toBe(200);
  expect(download.headers()["content-type"]).toContain("application/pdf");
  const foreignDocument = await page.request.get(`${process.env.PW_BASE_URL}/api/v1/investor/documents/${ids.documentBId}/download`);
  expect(foreignDocument.status()).toBe(404);
});

test("investor document library renders its permitted documents", async ({ page }) => {
  await loginInvestor(page);
  await page.goto("/investors/portal/documents");
  await expect(page.getByText("Synthetic investor A report").first()).toBeVisible();
  await expect(page.getByText("Synthetic investor B private report")).toHaveCount(0);
});
