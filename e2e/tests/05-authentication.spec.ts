import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { customerBEmail, customerEmail, loginCustomer, loginAdmin, ids } from "../test-helpers";

test("forgot-password uses a generic response without sending email", async ({ page }) => {
  await page.goto("/forgot-password");
  await page.getByLabel("Email").fill(customerEmail);
  await page.getByRole("button", { name: /Request reset link/ }).click();
  await expect(page.getByText(/If an account exists/i)).toBeVisible();
});

test("administrator reset link changes password and revokes the existing session", async ({ browser }) => {
  test.setTimeout(90_000);
  const customerContext = await browser.newContext();
  const customerPage = await customerContext.newPage();
  await loginCustomer(customerPage);
  const beforeReset = await customerPage.request.get(`${process.env.PW_BASE_URL}/api/v1/customer/me`);
  expect(beforeReset.status()).toBe(200);

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  await loginAdmin(adminPage);
  await adminPage.goto(`/admin/customers/${ids.customerAId}`);
  await adminPage.getByRole("button", { name: "Send password reset link" }).click();
  await adminPage.getByRole("button", { name: "Issue reset link" }).click();
  const link = adminPage.getByRole("textbox", { name: "password reset link" });
  await expect(link).toBeVisible();
  const resetUrl = await link.inputValue();
  await customerPage.goto(resetUrl);
  await customerPage.getByLabel("New password", { exact: true }).fill(process.env.PW_RESET_PASSWORD!);
  await customerPage.getByLabel("Confirm password", { exact: true }).fill(process.env.PW_RESET_PASSWORD!);
  await customerPage.getByRole("button", { name: "Save password" }).click();
  await expect(customerPage.getByText(/any other signed-in sessions were signed out/i)).toBeVisible();
  const revoked = await customerPage.request.get(`${process.env.PW_BASE_URL}/api/v1/customer/me`);
  expect(revoked.status()).toBe(401);

  await customerPage.goto("/login");
  const form = customerPage.getByRole("form", { name: "Sign in" });
  await form.getByLabel("Email").fill(customerEmail);
  await form.getByLabel("Password", { exact: true }).fill(process.env.PW_RESET_PASSWORD!);
  await form.getByRole("button", { name: "Sign in" }).click();
  await customerPage.waitForURL(/\/account(?:$|\/)/);
  await customerContext.close();
  await adminContext.close();
});

test("expired portal sessions are rejected", async ({ page }) => {
  await loginCustomer(page, customerBEmail);
  try {
    execFileSync("backend/.venv/bin/python", ["e2e/expire_session.py", customerBEmail], {
      env: { ...process.env, PYTHONPATH: "backend" },
      stdio: "pipe",
      encoding: "utf-8",
    });
  } catch (err: unknown) {
    const error = err as { stdout?: string; stderr?: string; message?: string };
    const details = [error.message, error.stderr, error.stdout].filter(Boolean).join("\n--- Subprocess Output ---\n");
    throw new Error(`Failed to execute expire_session.py for ${customerBEmail}:\n${details}`);
  }
  const expired = await page.request.get(`${process.env.PW_BASE_URL}/api/v1/customer/me`);
  expect(expired.status()).toBe(401);
  await page.goto("/account");
  await expect(page).toHaveURL(/\/login/);
});
