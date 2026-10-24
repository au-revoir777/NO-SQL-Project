import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

async function signIn(page: Page) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS.analyst.email);
  await page.getByLabel("Password").fill(E2E_USERS.analyst.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

async function noSeriousAxe(page: Page) {
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => a.playState !== "running"),
  );
  const { violations } = await new AxeBuilder({ page }).analyze();
  const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    bad.map((v) => `${v.id}: ${v.help}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

/** Ring A's members as the README's "What is planted" table states them. */
function readmeRingA(): { device: string; users: string[] } {
  const readme = readFileSync("../README.md", "utf-8");
  const row = readme.split(/\r?\n/).find((l) => l.startsWith("| Ring A |"));
  const m = row?.match(/\| Ring A \| ((?:u\d+, )*u\d+) share `(device_\d+)`/);
  if (!m) throw new Error("Ring A row not found in README.md");
  return { users: m[1]!.split(", "), device: m[2]! };
}

test("search device_007 on the course graph: the four users of Ring A in the README", async ({
  page,
}) => {
  const ringA = readmeRingA();
  expect(ringA).toEqual({ device: "device_007", users: ["u01", "u02", "u03", "u04"] });
  await signIn(page);
  await page.goto("/explorer?source=course");
  await page.getByLabel("Id starts with").fill(ringA.device);
  const results = page.getByRole("region", { name: "Search results" });
  await expect(results.getByRole("row")).toHaveCount(2); // header + one hit
  await noSeriousAxe(page);
  await results.getByRole("link", { name: ringA.device }).click();
  await expect(page).toHaveURL(/\/explorer\/device\/device_007\?source=course$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(ringA.device);
  const users = page.getByRole("region", { name: "Users linked to this attribute" });
  await expect(users.getByRole("link")).toHaveText(ringA.users);
  // The graph is drawn: Cytoscape's canvases hold non-transparent pixels.
  await expect
    .poll(() =>
      page.getByRole("img", { name: /^Neighbourhood graph/ }).evaluate((box) =>
        [...box.querySelectorAll("canvas")].some((c) => {
          const ctx = c.getContext("2d");
          if (!ctx || !c.width || !c.height) return false;
          const px = ctx.getImageData(0, 0, c.width, c.height).data;
          for (let i = 3; i < px.length; i += 4) if (px[i]! > 0) return true;
          return false;
        }),
      ),
    )
    .toBe(true);
  // The neighbourhood (k = 1) holds the same four users and the device as its seed.
  await page.getByRole("button", { name: /^Show the node table/ }).click();
  const nodes = page.getByRole("region", { name: "Neighbourhood nodes" });
  for (const u of ringA.users) await expect(nodes.getByRole("link", { name: u })).toBeVisible();
  await noSeriousAxe(page);
});

test("the walk stops at the office-wifi hub, expands on demand, and compares two pins", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/explorer/user/u13?source=course");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("u13");
  // ip_001 has 12 users (README: the hub, not fraud); a first-hop cap of 10 stops there.
  await page.getByLabel("First-hop cap").fill("10");
  await page.getByLabel("First-hop cap").blur();
  await page.getByRole("button", { name: /^Show the node table/ }).click();
  const nodes = page.getByRole("region", { name: "Neighbourhood nodes" });
  await expect(
    nodes
      .getByRole("row", { name: /ip_001/ })
      .getByText("stopped: hub: 12 active users > cap 10 at hop 1"),
  ).toBeVisible();
  const before = await nodes.getByRole("row").count();
  await nodes
    .getByRole("button", { name: /^Expand / })
    .first()
    .click();
  await expect.poll(async () => nodes.getByRole("row").count()).toBeGreaterThan(before);

  // Pin u01, open u02 and compare: both reach the other Ring A members via device_007.
  await page.goto("/explorer/user/u01?source=course");
  await page.getByRole("button", { name: "Pin to compare" }).click();
  await page.goto("/explorer/user/u02?source=course");
  await page.getByRole("button", { name: "Compare with user:u01" }).click();
  await expect(page.getByText(/Users reached from both: 4 \(u01, u02, u03, u04\)/)).toBeVisible();
});

test("Ctrl+K finds card_005 and opens it", async ({ page }) => {
  await signIn(page);
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Search entities" });
  await dialog.getByRole("button", { name: "Course seed graph" }).click();
  await dialog.getByRole("combobox", { name: "Entity id" }).fill("card_005");
  await expect(dialog.getByRole("option", { name: /card_005/ })).toBeVisible();
  await noSeriousAxe(page);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/explorer\/card\/card_005\?source=course$/);
  await expect(
    page.getByRole("region", { name: "Users linked to this attribute" }).getByRole("link"),
  ).toHaveText(["u10", "u11", "u12"]);
});

test("an alert of the current run opens its ring over time", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  const csrf = (await page.context().cookies()).find((c) => c.name === "fraudsim_csrf")?.value;
  const res = await page.request.post("/api/v1/runs", {
    data: { scenario: "baseline", seed: 7, speed_multiplier: 0 },
    headers: { "x-csrf-token": csrf ?? "" },
  });
  expect(res.status(), await res.text()).toBe(201);
  await expect
    .poll(
      async () => (await (await page.request.get("/api/v1/runs/current")).json()).status as string,
      { timeout: 90_000 },
    )
    .toBe("finished");
  await page.goto("/alerts");
  const first = page.getByRole("region", { name: "Alerts" }).getByRole("link").first();
  const ref = (await first.textContent())!.trim();
  await first.click();
  await page.getByRole("link", { name: "Ring in explorer" }).click();
  await expect(page).toHaveURL(new RegExp(`/explorer/rings/${ref}$`));
  await expect(page.getByRole("heading", { level: 1 })).toContainText(ref);
  const changes = page.getByRole("region", { name: "Membership changes" });
  await expect(changes.getByRole("row").nth(1)).toContainText("created");
  await noSeriousAxe(page);
});
