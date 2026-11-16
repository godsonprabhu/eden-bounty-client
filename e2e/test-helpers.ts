import { execFileSync } from "node:child_process";
import type { Page } from "@playwright/test";

export type FixtureIds = {
  adminId: string;
  customerAId: string;
  customerBId: string;
  enquiryId: string;
  orderAId: string;
  orderBId: string;
  investorAId: string;
  investorBId: string;
  documentAId: string;
  documentBId: string;
};

export const ids = JSON.parse(process.env.PW_FIXTURE_IDS ?? "{}") as FixtureIds;
export const testPassword = required("PW_TEST_PASSWORD");
export const adminEmail = required("PW_ADMIN_EMAIL");
export const customerEmail = required("PW_CUSTOMER_EMAIL");
export const customerBEmail = required("PW_CUSTOMER_B_EMAIL");
export const investorEmail = required("PW_INVESTOR_EMAIL");
export const newCustomerEmail = required("PW_NEW_CUSTOMER_EMAIL");

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required. Run npm run test:e2e:local.`);
  return value;
}

export async function loginAdmin(page: Page) {
  await page.goto("/login");
  const form = page.getByRole("form", { name: "Sign in" });
  await form.getByLabel("Email").fill(adminEmail);
  await form.locator('input[autocomplete="current-password"]').fill(testPassword);
  await form.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/admin(?:$|\/)/);
}

export async function loginCustomer(page: Page, email = customerEmail) {
  await page.goto("/login");
  const form = page.getByRole("form", { name: "Sign in" });
  await form.getByLabel("Email").fill(email);
  await form.locator('input[autocomplete="current-password"]').fill(testPassword);
  await form.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/account(?:$|\/)/);
}

export async function loginInvestor(page: Page) {
  await page.goto("/investors/login");
  const form = page.getByRole("form", { name: "Investor sign in" });
  await form.getByLabel("Email").fill(investorEmail);
  await form.locator('input[autocomplete="current-password"]').fill(testPassword);
  await form.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/investors\/portal(?:$|\/)/);
}

export function getVerificationLinkCLI(email: string): string {
  try {
    const output = execFileSync(
      "backend/.venv/bin/python",
      ["-m", "app.cli.verify_account", "--email", email, "--show-link"],
      {
        env: { ...process.env, PYTHONPATH: "backend" },
        encoding: "utf-8",
        stdio: "pipe",
      }
    );
    const match = output.match(/https?:\/\/[^\s]+/);
    if (!match) {
      throw new Error(`No verification link found in CLI output:\n${output}`);
    }
    return match[0];
  } catch (err: unknown) {
    const error = err as { stdout?: string; stderr?: string; message?: string };
    const details = [error.message, error.stderr, error.stdout].filter(Boolean).join("\n--- Subprocess Output ---\n");
    throw new Error(`Failed to generate verification link via CLI for ${email}:\n${details}`);
  }
}

export function verifyAccountCLI(email: string): void {
  try {
    execFileSync(
      "backend/.venv/bin/python",
      ["-m", "app.cli.verify_account", "--email", email],
      {
        env: { ...process.env, PYTHONPATH: "backend" },
        encoding: "utf-8",
        stdio: "pipe",
      }
    );
  } catch (err: unknown) {
    const error = err as { stdout?: string; stderr?: string; message?: string };
    const details = [error.message, error.stderr, error.stdout].filter(Boolean).join("\n--- Subprocess Output ---\n");
    throw new Error(`Failed to directly verify account via CLI for ${email}:\n${details}`);
  }
}

