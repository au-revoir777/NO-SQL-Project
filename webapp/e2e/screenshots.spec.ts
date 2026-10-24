import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

/**
 * README screenshots of the real app (login, users admin, 403 page).
 * Skipped unless SCREENSHOTS=1:  SCREENSHOTS=1 npx playwright test screenshots
 */
test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to refresh the README screenshots");

const OUT = "../docs/images";

async function signIn(page: Page, who: keyof typeof E2E_USERS) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS[who].email);
  await page.getByLabel("Password").fill(E2E_USERS[who].password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");
}

test.use({ viewport: { width: 1280, height: 800 } });

test("login page", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.screenshot({ path: `${OUT}/webapp_p2_login.png` });
});

test("users admin page", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/users");
  await expect(page.getByText(E2E_USERS.analyst.email)).toBeVisible();
  await page.screenshot({ path: `${OUT}/webapp_p2_users_admin.png` });
});

test("analyst sees the 403 page", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/users");
  await expect(page.getByRole("heading", { name: "403: Access denied" })).toBeVisible();
  await page.screenshot({ path: `${OUT}/webapp_p2_forbidden.png` });
});

test("live dashboard after a baseline run", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page, "analyst");
  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  const started = await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 2 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  const runId = ((await started.json()) as { run_id: string }).run_id;
  const header = page.getByText(`Run ${runId}`);
  await expect(header).toBeVisible({ timeout: 30_000 });
  await expect(header).toContainText("finished", { timeout: 90_000 });
  await page.getByRole("button", { name: "Oracle (simulator ground truth)" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/webapp_p3_dashboard.png`, fullPage: true });
});
