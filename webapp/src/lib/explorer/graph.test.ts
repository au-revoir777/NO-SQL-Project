import { describe, expect, it } from "vitest";

import {
  compareUsers,
  fromUtcInput,
  mergeNeighbourhoods,
  type Neighbourhood,
  parseKey,
  toUtcInput,
} from "./graph";

// Test fixtures shaped like GET /api/v1/graph/neighbourhood (not results).
function nb(nodes: Partial<Neighbourhood["nodes"][number]>[], truncated = false): Neighbourhood {
  return {
    source: "course",
    params: {},
    truncated,
    nodes: nodes.map((n) => ({
      key: `${n.kind}:${n.id}`,
      kind: "user",
      id: "x",
      hop: 0,
      seed: false,
      stop: null,
      ...n,
    })) as Neighbourhood["nodes"],
    edges: [],
  };
}

describe("explorer graph helpers", () => {
  it("parses node keys", () => {
    expect(parseKey("device:device_007")).toEqual({ kind: "device", id: "device_007" });
    expect(parseKey("ip:10.0.0.1:443")).toEqual({ kind: "ip", id: "10.0.0.1:443" });
    expect(parseKey("bogus")).toBeNull();
    expect(parseKey("planet:x")).toBeNull();
  });

  it("merges neighbourhoods: smallest hop, seeds, crossed stops, origins", () => {
    const stop = { hop: 1, degree: 12, cap: 3, reason: "hub" };
    const a = nb([
      { kind: "user", id: "u01", hop: 0, seed: true },
      { kind: "user", id: "u02", hop: 1 },
      { kind: "ip", id: "ip_001", hop: 1, stop },
    ]);
    const b = nb(
      [
        { kind: "user", id: "u02", hop: 0, seed: true },
        { kind: "ip", id: "ip_001", hop: 1, stop: null },
        { kind: "user", id: "u13", hop: 1 },
      ],
      true,
    );
    const g = mergeNeighbourhoods([
      { label: "A", nb: a },
      { label: "B", nb: b },
    ]);
    const by = Object.fromEntries(g.nodes.map((n) => [n.key, n]));
    expect(by["user:u02"]).toMatchObject({ hop: 0, seed: true, from: ["A", "B"] });
    expect(by["ip:ip_001"]!.stop).toBeNull(); // B crossed it
    expect(g.truncated).toBe(true);
    expect(compareUsers(g, "A", "B")).toEqual({ onlyA: ["u01"], onlyB: ["u13"], both: ["u02"] });
  });

  it("reads the time window as UTC", () => {
    expect(toUtcInput(1767225600)).toBe("2026-01-01T00:00:00");
    expect(fromUtcInput("2026-01-01T00:00")).toBe(1767225600);
    expect(fromUtcInput("")).toBeNull();
    expect(toUtcInput(null)).toBe("");
  });
});
