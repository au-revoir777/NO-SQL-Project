import { describe, expect, it } from "vitest";

import presets from "./presets.fixture.json";
import {
  emptyRing,
  formPath,
  fromScenario,
  type ScenarioV1,
  scenarioFormSchema,
  toScenario,
} from "./scenario-form";

// The seven presets as the API returns them (generated from configs/scenarios/*.yaml
// by api/v1/schemas/scenario.py; regenerate when a preset changes).
const all = presets as unknown as Record<string, ScenarioV1>;

describe("scenario form", () => {
  it.each(Object.keys(all))("%s round-trips through the form unchanged", (name) => {
    const form = fromScenario(all[name]!);
    expect(scenarioFormSchema.safeParse(form).success).toBe(true);
    expect(toScenario(form)).toEqual(all[name]);
  });

  it("leaves empty optional fields out instead of sending 0", () => {
    const form = fromScenario(all.baseline!);
    form.sim.amount_median = "";
    form.rings = [emptyRing(0)];
    const out = toScenario(form);
    expect("amount_median" in out.simulation).toBe(false);
    expect(out.rings?.[0]).toEqual({
      id: "ring_1",
      type: "shared_device",
      size: 4,
      spawn_time_s: 10,
      evasion: "none",
    });
  });

  it("rejects bad numbers with field messages", () => {
    const form = fromScenario(all.baseline!);
    form.sim.num_users = "1.5";
    form.sim.heavy_tail_alpha = "1";
    const res = scenarioFormSchema.safeParse(form);
    expect(res.success).toBe(false);
    const issues = Object.fromEntries(res.error!.issues.map((i) => [i.path.join("."), i.message]));
    expect(issues["sim.num_users"]).toBe("Enter a whole number");
    expect(issues["sim.heavy_tail_alpha"]).toBe("More than 1");
  });

  it("maps server error locations to form fields", () => {
    const form = fromScenario(all.demo_story!);
    expect(formPath(["body", "simulation", "num_users"], form)).toBe("sim.num_users");
    expect(formPath(["body", "rings", 1, "size"], form)).toBe("rings.1.size");
    expect(formPath(["body", "simulation", "hub_distribution", "office_wifi", "size"], form)).toBe(
      "hubs.0.size",
    );
  });
});
