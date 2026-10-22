import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

async function signIn(page: Page, who: keyof typeof E2E_USERS) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS[who].email);
  await page.getByLabel("Password").fill(E2E_USERS[who].password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test("anonymous visitors are sent to the login page", async ({ page }) => {
  await page.goto("/cases");
  await expect(page).toHaveURL(/\/login\?next=%2Fcases/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("a wrong password is refused with a clear message", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS.analyst.email);
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("analyst: admin pages are hidden and a direct URL returns the 403 page", async ({ page }) => {
  await signIn(page, "analyst");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Alerts" })).toBeVisible();
  for (const name of ["Rules", "Users", "Audit"]) {
    await expect(nav.getByRole("link", { name })).toHaveCount(0);
  }
  for (const path of ["/rules", "/users", "/audit"]) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(403);
    await expect(page.getByRole("heading", { name: "403: Access denied" })).toBeVisible();
  }
});

test("admin: the rules page is visible and users can be managed", async ({ page }) => {
  await signIn(page, "admin");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await nav.getByRole("link", { name: "Rules" }).click();
  await expect(page).toHaveURL("/rules");
  await expect(page.getByRole("heading", { name: "Rules", level: 1 })).toBeVisible();

  await nav.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users", level: 1 })).toBeVisible();
  await expect(page.getByText(E2E_USERS.analyst.email)).toBeVisible();

  const email = `new.${Date.now()}@example.test`;
  await page.getByRole("button", { name: "New user" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("a-new-user-password");
  await page.getByRole("button", { name: "Create user" }).click();
  await expect(page.getByRole("row").filter({ hasText: email })).toBeVisible();
});

test("signing out ends the session", async ({ page }) => {
  await signIn(page, "analyst");
  await page.getByRole("button", { name: /Account:/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
});
