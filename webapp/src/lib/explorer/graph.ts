/**
 * Pure helpers for the graph explorer: merging neighbourhoods (expand on
 * click, pin and compare), and the UTC time window. Tested in graph.test.ts.
 */
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
export type GraphNode = S["GraphNodeOut"];
export type GraphEdge = S["GraphEdgeOut"];
export type Neighbourhood = S["NeighbourhoodOut"];
export type EntityKind = GraphNode["kind"];
export type Source = Neighbourhood["source"];
export type Rel = GraphEdge["kind"];

export const KINDS: EntityKind[] = ["user", "device", "card", "ip"];
export const RELS: Rel[] = ["device", "card", "ip", "transfer"];
export const KIND_LABEL: Record<EntityKind, string> = {
  user: "User",
  device: "Device",
  card: "Card",
  ip: "IP address",
};
export const SOURCE_LABEL: Record<Source, string> = {
  run: "Current run",
  course: "Course seed graph",
  neo4j: "Neo4j database",
};

export function nodeKey(kind: EntityKind, id: string): string {
  return `${kind}:${id}`;
}

/** "device:device_007" -> {kind, id}; null when malformed. */
export function parseKey(key: string): { kind: EntityKind; id: string } | null {
  const i = key.indexOf(":");
  const kind = key.slice(0, i) as EntityKind;
  const id = key.slice(i + 1);
  return i > 0 && id && KINDS.includes(kind) ? { kind, id } : null;
}

export interface MergedNode extends GraphNode {
  /** Labels of the neighbourhoods that contain this node (e.g. "A", "B"). */
  from: string[];
}

export interface MergedGraph {
  nodes: MergedNode[];
  edges: GraphEdge[];
  truncated: boolean;
}

/**
 * Union of neighbourhoods by node key. A node keeps the smallest hop, is a seed
 * if it is a seed anywhere, keeps a stop reason only if every part stopped
 * there (an expansion that crossed it wins), and records which parts reached it.
 */
export function mergeNeighbourhoods(parts: { label: string; nb: Neighbourhood }[]): MergedGraph {
  const nodes = new Map<string, MergedNode>();
  const edges = new Map<string, GraphEdge>();
  let truncated = false;
  for (const { label, nb } of parts) {
    truncated ||= nb.truncated;
    for (const n of nb.nodes) {
      const prev = nodes.get(n.key);
      if (!prev) {
        nodes.set(n.key, { ...n, from: [label] });
        continue;
      }
      nodes.set(n.key, {
        ...prev,
        hop: Math.min(prev.hop, n.hop),
        seed: prev.seed || n.seed,
        stop: prev.stop && n.stop ? prev.stop : null,
        from: prev.from.includes(label) ? prev.from : [...prev.from, label],
      });
    }
    for (const e of nb.edges) edges.set(e.id, e);
  }
  return {
    nodes: [...nodes.values()].sort((a, b) => a.hop - b.hop || a.key.localeCompare(b.key)),
    edges: [...edges.values()].sort((a, b) => a.id.localeCompare(b.id)),
    truncated,
  };
}

/** Users reached from A only, from B only, and from both. */
export function compareUsers(g: MergedGraph, a: string, b: string) {
  const users = g.nodes.filter((n) => n.kind === "user");
  const has = (n: MergedNode, l: string) => n.from.includes(l);
  return {
    onlyA: users.filter((n) => has(n, a) && !has(n, b)).map((n) => n.id),
    onlyB: users.filter((n) => has(n, b) && !has(n, a)).map((n) => n.id),
    both: users.filter((n) => has(n, a) && has(n, b)).map((n) => n.id),
  };
}

/** Simulated epoch seconds <-> a datetime-local value read as UTC. */
export function toUtcInput(t: number | null | undefined): string {
  if (t === null || t === undefined) return "";
  return new Date(t * 1000).toISOString().slice(0, 19);
}

export function fromUtcInput(v: string): number | null {
  if (!v) return null;
  const ms = Date.parse(`${v.length === 16 ? `${v}:00` : v}Z`);
  return Number.isFinite(ms) ? ms / 1000 : null;
}

export function fmtSimTime(t: number | null | undefined): string {
  if (t === null || t === undefined) return "–";
  return `${new Date(t * 1000).toISOString().slice(0, 19).replace("T", " ")} UTC`;
}
