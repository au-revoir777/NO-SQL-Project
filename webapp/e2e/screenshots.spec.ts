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

test("simulator during a demo_story run", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page, "analyst");
  await page.goto("/simulator");
  await page.getByLabel("Preset").selectOption("demo_story");
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("demo_story");
  await page.getByLabel("Seed").fill("7");
  await page.getByLabel(/^Speed \(simulated/).fill("3");
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByText(/active users shown/)).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(12_000);
  await page.screenshot({ path: `${OUT}/webapp_p4_simulator.png`, fullPage: true });
});

test("story replay", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/replays/00434da7845b?t=60&det=system&key=1");
  await expect(page.getByRole("heading", { name: /Replay of run/ })).toBeVisible();
  await page.screenshot({ path: `${OUT}/webapp_p4_replay.png`, fullPage: true });
});

test("P5: alert queue, alert evidence, case and audit view", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page, "analyst");
  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
  await page.goto("/alerts");
  const first = page.getByRole("table").getByRole("link").first();
  await expect(first).toBeVisible();
  await page.screenshot({ path: `${OUT}/webapp_p5_alerts.png`, fullPage: true });

  const ref = (await first.textContent())!.trim();
  await first.click();
  await page.getByRole("tab", { name: "Evidence" }).click();
  await page.waitForTimeout(1_000);
  await page.screenshot({ path: `${OUT}/webapp_p5_alert_evidence.png`, fullPage: true });

  await page.getByRole("tab", { name: "Activity" }).click();
  await page.getByLabel("Add a note").fill("Four accounts opened within a minute on one device.");
  await page.getByRole("button", { name: "Add note" }).click();
  await page.getByRole("button", { name: "Confirmed fraud" }).click();
  await expect(page.getByText(/Threshold for .*→/)).toBeVisible();
  await page.getByRole("button", { name: "Create case" }).click();
  await page.getByLabel("Title").fill(`Ring ${ref}: shared attributes and transfers`);
  await page.getByRole("dialog").getByRole("button", { name: "Create case" }).click();
  await expect(page).toHaveURL(/\/cases\/\d+$/);
  await page.getByRole("combobox", { name: "Move to" }).click();
  await page.getByRole("option", { name: "escalated" }).click();
  await page.getByRole("button", { name: "Update status" }).click();
  await expect(page.getByText("Case moved to escalated.")).toBeVisible();
  await page.waitForTimeout(4_500); // let the toast fade
  await page.screenshot({ path: `${OUT}/webapp_p5_case.png`, fullPage: true });

  await page.context().clearCookies();
  await signIn(page, "admin");
  await page.goto("/audit");
  await expect(page.getByText("Hash chain intact")).toBeVisible();
  await page.screenshot({ path: `${OUT}/webapp_p5_audit.png`, fullPage: true });
});

test("P6: entity page, hub stop and ring view", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page, "analyst");
  await page.goto("/explorer/device/device_007?source=course");
  await expect(page.getByRole("button", { name: /^Show the node table \([1-9]/ })).toBeVisible();
  await page.waitForTimeout(1_500);
  await page.screenshot({ path: `${OUT}/webapp_p6_entity.png`, fullPage: true });

  await page.goto("/explorer/user/u13?source=course");
  await page.getByLabel("Hops (k)").click();
  await page.getByRole("option", { name: "2" }).click();
  await page.getByLabel("First-hop cap").fill("10");
  await page.getByLabel("First-hop cap").blur();
  await expect(page.getByText(/hub: 12 active users > cap 10/).first()).toBeVisible();
  await page.waitForTimeout(1_500);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${OUT}/webapp_p6_hub_stop.png`, fullPage: true });

  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
  const alerts = (await (await page.request.get("/api/v1/alerts")).json()) as {
    items: { alert_ref: string; members_count: number }[];
  };
  const ring = [...alerts.items].sort((a, b) => b.members_count - a.members_count)[0]!;
  await page.goto(`/explorer/rings/${ring.alert_ref}`);
  await expect(page.getByRole("region", { name: "Membership changes" })).toBeVisible();
  await page.waitForTimeout(1_500);
  await page.screenshot({ path: `${OUT}/webapp_p6_ring.png`, fullPage: true });
});
