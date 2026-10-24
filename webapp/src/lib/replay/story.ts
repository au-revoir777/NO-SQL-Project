/**
 * The story replay of `fraudsim demo-story`, as pure functions ported from
 * src/fraudsim/demo/story_template.html (kept unchanged at demo/story.html):
 * the same state-at-time rule, the same deterministic layout and the same deep
 * links, so the web page and the HTML file show identical numbers.
 */

export interface StoryFlag {
  t_s: number;
  batch?: number;
  ring_id: string;
  kind: "flag" | "early_warning" | string;
  members: string[];
  detectors?: string[];
  risk: number | null;
  true_ring: string | null;
  jaccard?: number;
  explanation?: {
    reason: string;
    threshold?: number;
    counterfactual?: string | null;
    contributions: { label: string; feature?: string; value: number }[];
  };
}

export interface StoryApproach {
  key: string;
  title: string;
  subtitle: string;
  flag_rule: string;
  caught: { true_ring: string; ring_id: string; jaccard: number; flagged_s: number }[];
  missed: string[];
  false_rings: number;
  benign_users_flagged: number;
  log: StoryFlag[];
}

export interface StoryTruth {
  ring_id: string;
  type: string;
  evasion: string;
  members: string[];
  spawn_s: number | null;
  activate_s: number | null;
}

export interface StoryNode {
  id: string;
  kind: string;
  truth: string;
  hub?: string;
  hub_category?: string;
  degree?: number;
  appear_s: number;
  left_s?: number | null;
}

export interface StoryEdge {
  s: string;
  t: string;
  type: string;
  appear_s: number;
}

export interface StoryTransfer {
  s: string;
  t: string;
  at: number;
}

export interface Story {
  meta: {
    run_id: string;
    scenario: string;
    seed: number;
    config_hash: string;
    scenario_hash: string;
    stream_digest: string;
    events: number;
    duration_s: number;
    generated_at: string;
    match_rule: string;
    command: string;
    batch_size: number;
    full_interval_s: number;
    model: {
      type: string;
      training_id: string;
      train_seeds?: number[];
      test_seeds?: number[];
      test_metrics?: { roc_auc?: number; brier?: number };
    } | null;
  };
  truth: StoryTruth[];
  approaches: StoryApproach[];
  spotlight: Record<string, unknown> & { found?: boolean };
  graph: { nodes: StoryNode[]; edges: StoryEdge[]; transfers?: StoryTransfer[] };
}

export const SHORT_NAME: Record<string, string> = {
  cap10: "Cap 10",
  cap100: "Cap 100",
  system: "Hub-aware",
};

export interface DetectorState {
  flagged: Set<string>;
  caught: Set<string>;
  falseFlags: number;
  items: StoryFlag[];
}

/** Flags of one detector up to time t (the template's stateAt). */
export function stateAt(log: StoryFlag[], time: number): DetectorState {
  const flagged = new Set<string>();
  const caught = new Set<string>();
  let falseFlags = 0;
  const items: StoryFlag[] = [];
  for (const f of log) {
    if (f.t_s > time) break;
    items.push(f);
    if (f.kind !== "flag") continue;
    f.members.forEach((u) => flagged.add(u));
    if (f.true_ring) caught.add(f.true_ring);
    else falseFlags++;
  }
  return { flagged, caught, falseFlags, items };
}

/** Each detector's log, sorted by time (as the template does). */
export function sortedLogs(story: Story): Record<string, StoryFlag[]> {
  return Object.fromEntries(
    story.approaches.map((a) => [a.key, (a.log ?? []).slice().sort((x, y) => x.t_s - y.t_s)]),
  );
}

export interface DeepLink {
  t?: number;
  det?: string;
  key?: boolean;
}

/**
 * Deep links `?t=60&det=cap10&key=1`; the old `#t=…&det=…&key=1` form of
 * story.html is accepted too (the query string wins when both are given).
 */
export function parseDeepLink(search: string, hash: string, duration: number): DeepLink {
  const out: DeepLink = {};
  for (const params of [new URLSearchParams(hash.replace(/^#/, "")), new URLSearchParams(search)]) {
    const t = params.get("t");
    if (t !== null && !Number.isNaN(Number(t))) out.t = Math.max(0, Math.min(duration, Number(t)));
    const det = params.get("det");
    if (det) out.det = det;
    const key = params.get("key");
    if (key !== null) out.key = key === "1";
  }
  return out;
}

export interface PlacedNode extends StoryNode {
  x: number;
  y: number;
}

export const LAYOUT_W = 1000;
export const LAYOUT_H = 600;

/** The template's deterministic force layout (seeded, 500 iterations, computed once). */
export function layout(story: Story): Map<string, PlacedNode> {
  const W = LAYOUT_W;
  const H = LAYOUT_H;
  const G = story.graph;
  const nodes = G.nodes.map((n) => ({ ...n, x: 0, y: 0, vx: 0, vy: 0 }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ringOfUser: Record<string, string> = {};
  story.truth.forEach((t) => t.members.forEach((u) => (ringOfUser[u] = t.ring_id)));
  const links = G.edges
    .filter((e) => byId.has(e.s) && byId.has(e.t))
    .map((e) => ({ ...e, a: byId.get(e.s)!, b: byId.get(e.t)! }));
  const transfers = (G.transfers ?? [])
    .filter((e) => byId.has(e.s) && byId.has(e.t))
    .map((e) => ({ ...e, type: "transfer", a: byId.get(e.s)!, b: byId.get(e.t)! }));
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const ringIds = story.truth.map((r) => r.ring_id);
  nodes.forEach((n) => {
    const ri = ringIds.indexOf(n.truth);
    const cx = ri >= 0 ? W * (0.18 + (0.64 * ri) / Math.max(1, ringIds.length - 1)) : W * 0.5;
    n.x = cx + (rnd() - 0.5) * 320;
    n.y = H / 2 + (rnd() - 0.5) * 320;
  });
  const springs = [
    ...links,
    ...transfers.filter(
      (x, i, arr) =>
        arr.findIndex((y) => y.s === x.s && y.t === x.t) === i &&
        ringOfUser[x.s] &&
        ringOfUser[x.t],
    ),
  ];
  for (let it = 0; it < 500; it++) {
    const alpha = 1 - it / 500;
    for (let i = 0; i < nodes.length; i++)
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i]!;
        const b = nodes[j]!;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        if (d2 > 40000) continue;
        const f = (260 / d2) * alpha;
        a.vx += dx * f;
        a.vy += dy * f;
        b.vx -= dx * f;
        b.vy -= dy * f;
      }
    for (const l of springs) {
      const dx = l.b.x - l.a.x;
      const dy = l.b.y - l.a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const want = l.type === "link" ? (l.b.hub || l.a.hub ? 150 : 35) : 40;
      const f = ((d - want) / d) * 0.05 * alpha;
      l.a.vx += dx * f;
      l.a.vy += dy * f;
      l.b.vx -= dx * f;
      l.b.vy -= dy * f;
    }
    for (const n of nodes) {
      n.vx += (W / 2 - n.x) * 0.012 * alpha;
      n.vy += (H / 2 - n.y) * 0.02 * alpha;
      n.x += n.vx;
      n.y += n.vy;
      n.vx *= 0.55;
      n.vy *= 0.55;
      n.x = Math.max(16, Math.min(W - 16, n.x));
      n.y = Math.max(22, Math.min(H - 16, n.y));
    }
  }
  return new Map<string, PlacedNode>(nodes.map((n) => [n.id, n]));
}
