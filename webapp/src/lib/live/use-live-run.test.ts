import { describe, expect, it } from "vitest";

import { windowedRate } from "./use-live-run";

describe("windowedRate", () => {
  it("is the event rate between consecutive samples", () => {
    const samples = [
      { events_total: 500, wall_s: 0.1 }, // start-up burst
      { events_total: 530, wall_s: 1.1 },
      { events_total: 560, wall_s: 2.1 },
      { events_total: 560, wall_s: 2.1 }, // no wall time passed
    ];
    expect(windowedRate(samples)).toEqual([null, 30, 30, null]);
  });
});
