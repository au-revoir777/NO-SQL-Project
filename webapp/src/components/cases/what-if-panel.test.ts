import { describe, expect, it } from "vitest";

import { sliderRange } from "./what-if-panel";

describe("what-if slider ranges", () => {
  it("keep shares in [0, 1], sizes in whole members, and leave room above the scored value", () => {
    expect(sliderRange({ name: "density", original: 0.4 })).toEqual({ max: 1, step: 0.01 });
    expect(sliderRange({ name: "size", original: 3 })).toEqual({ max: 10, step: 1 });
    expect(sliderRange({ name: "size", original: 9 })).toEqual({ max: 18, step: 1 });
    expect(sliderRange({ name: "internal_txns_per_member", original: 2.34 }).max).toBeCloseTo(4.7);
    expect(sliderRange({ name: "hub_exposure", original: 0 }).max).toBe(1);
  });
});
