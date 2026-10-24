import { describe, expect, it } from "vitest";

import { parseDeepLink, type StoryFlag, stateAt } from "./story";

const flag = (
  t_s: number,
  kind: string,
  true_ring: string | null,
  members: string[],
): StoryFlag => ({
  t_s,
  ring_id: `R${t_s}`,
  kind,
  members,
  risk: null,
  true_ring,
});

describe("stateAt", () => {
  const log = [
    flag(5, "early_warning", "ring_a", ["u1", "u2"]),
    flag(10, "flag", "ring_a", ["u1", "u2"]),
    flag(12, "flag", null, ["u7", "u8"]),
    flag(20, "flag", "ring_a", ["u1", "u3"]), // same true ring again: caught once
    flag(30, "flag", "ring_b", ["u4"]),
  ];

  it("counts only flags up to t; early warnings are listed but not counted", () => {
    const s = stateAt(log, 12);
    expect([...s.caught]).toEqual(["ring_a"]);
    expect(s.falseFlags).toBe(1);
    expect(s.items).toHaveLength(3);
    expect([...s.flagged].sort()).toEqual(["u1", "u2", "u7", "u8"]);
  });

  it("does not double count a true ring", () => {
    const s = stateAt(log, 25);
    expect(s.caught.size).toBe(1);
    expect(stateAt(log, 90).caught.size).toBe(2);
  });
});

describe("parseDeepLink", () => {
  it("reads the query string and the old hash form, clamping t", () => {
    expect(parseDeepLink("?t=90&det=cap10&key=1", "", 90)).toEqual({
      t: 90,
      det: "cap10",
      key: true,
    });
    expect(parseDeepLink("", "#t=60&det=system", 90)).toEqual({ t: 60, det: "system" });
    expect(parseDeepLink("?t=500", "", 90)).toEqual({ t: 90 });
    expect(parseDeepLink("?t=10", "#t=60&key=0", 90)).toEqual({ t: 10, key: false });
  });
});
