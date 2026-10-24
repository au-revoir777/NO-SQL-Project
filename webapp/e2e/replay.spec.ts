import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { E2E_USERS } from "../playwright.config";

const RUN = "00434da7845b";

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_USERS.analyst.email);
  await page.getByLabel("Password").fill(E2E_USERS.analyst.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

interface Flag {
  t_s: number;
  kind: string;
  true_ring: string | null;
}

/** The counters of demo/story.html (its stateAt), computed from the story JSON. */
function expected(log: Flag[], t: number) {
  const caught = new Set<string>();
  let falseFlags = 0;
  for (const f of [...log].sort((a, b) => a.t_s - b.t_s)) {
    if (f.t_s > t) break;
    if (f.kind !== "flag") continue;
    if (f.true_ring) caught.add(f.true_ring);
    else falseFlags++;
  }
  return { caught: caught.size, falseFlags };
}

test("replay at ?t=90&det=cap10&key=1 shows the same counts as the end of story.html", async ({
  page,
}) => {
  await signIn(page);
  const story = (await (await page.request.get(`/api/v1/replays/${RUN}`)).json()) as {
    meta: { duration_s: number };
    truth: unknown[];
    approaches: { key: string; log: Flag[] }[];
  };
  await page.goto(`/replays/${RUN}?t=90&det=cap10&key=1`);
  await expect(page.getByRole("heading", { name: `Replay of run ${RUN}` })).toBeVisible();
  await expect(page.getByLabel("Answer key (simulator ground truth)")).toBeChecked();
  await expect(
    page
      .getByRole("group", { name: "Detector" })
      .getByRole("button", { name: "Cap 10", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  for (const a of story.approaches) {
    const want = expected(a.log, 90);
    await expect(page.getByTestId(`caught-${a.key}`)).toHaveText(
      `${want.caught}/${story.truth.length}`,
    );
    await expect(page.getByTestId(`false-${a.key}`)).toHaveText(String(want.falseFlags));
  }
  // The old story.html deep-link form is accepted too.
  await page.goto(`/replays/${RUN}#t=30&det=system`);
  await expect(
    page
      .getByRole("group", { name: "Detector" })
      .getByRole("button", { name: "Hub-aware", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("output[for=scrub]")).toContainText("30.0 s");
});

test("replays list and replay page have no serious or critical axe violations", async ({
  page,
}) => {
  await signIn(page);
  for (const url of ["/replays", `/replays/${RUN}?t=45&det=system`]) {
    await page.goto(url);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    const { violations } = await new AxeBuilder({ page }).analyze();
    const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(
      bad.map((v) => `${v.id}: ${v.help}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
      url,
    ).toEqual([]);
  }
});
