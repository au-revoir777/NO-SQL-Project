/**
 * Scenario builder state <-> the API's ScenarioV1 (the YAML dialect).
 *
 * Numbers are kept as strings in the form, so an empty optional field is
 * simply left out of the scenario (as in YAML) instead of becoming 0 or NaN.
 * Named hubs are a list in the form and a mapping (`hub_distribution`) in the
 * scenario. The zod schema mirrors the server's field constraints (pydantic in
 * api/v1/schemas/scenario.py); the server stays the authority and its
 * field-level errors are shown on the same fields.
 */
import { z } from "zod";

import type { components } from "@/lib/api/schema";

/** What the API returns (GET /scenarios/{name}) and what it accepts (validate, yaml, runs). */
export type ScenarioV1 = components["schemas"]["ScenarioV1-Output"];
export type ScenarioIn = components["schemas"]["ScenarioV1-Input"];
type RingV1 = components["schemas"]["RingV1"];

type Bound = { min?: number; gt?: number; max?: number; int?: boolean };

/** A number typed into a text box: optional when empty unless `required`. */
function num({ min, gt, max, int }: Bound, required = false) {
  return z.string().superRefine((raw, ctx) => {
    const s = raw.trim();
    if (s === "") {
      if (required) ctx.addIssue({ code: "custom", message: "Required" });
      return;
    }
    const v = Number(s);
    if (!Number.isFinite(v)) return ctx.addIssue({ code: "custom", message: "Enter a number" });
    if (int && !Number.isInteger(v))
      return ctx.addIssue({ code: "custom", message: "Enter a whole number" });
    if (min !== undefined && v < min) ctx.addIssue({ code: "custom", message: `At least ${min}` });
    if (gt !== undefined && v <= gt) ctx.addIssue({ code: "custom", message: `More than ${gt}` });
    if (max !== undefined && v > max) ctx.addIssue({ code: "custom", message: `At most ${max}` });
  });
}

const hub = z.object({
  name: z.string().regex(/^[A-Za-z0-9_.-]{1,64}$/, "Letters, digits, _ . -"),
  type: z.enum(["device", "card", "ip"]),
  category: z.string(),
  size: num({ min: 2, max: 100_000, int: true }, true),
  fill_time_s: num({ min: 0 }),
  start_time_s: num({ min: 0 }),
});

const ring = z.object({
  id: z.string().min(1, "Required").max(64),
  type: z.string().min(1),
  size: num({ min: 2, max: 1000, int: true }, true),
  spawn_time_s: num({ min: 0 }, true),
  evasion: z.string(),
  shared_attribute: z.string().max(128),
  length: num({ min: 3, max: 6, int: true }),
  grow_interval_s: num({ gt: 0 }),
  initial_members: num({ min: 1, int: true }),
  active_duration_s: num({ gt: 0 }),
  action_interval_s: num({ gt: 0 }),
  mutate_prob: num({ min: 0, max: 1 }),
  intensity: num({ gt: 0 }),
});

export const scenarioFormSchema = z.object({
  name: z.string().regex(/^[a-z0-9][a-z0-9_]{0,63}$/, "Lower-case letters, digits and _"),
  description: z.string().max(500),
  version: z.string().max(20),
  sim: z.object({
    duration_seconds: num({ gt: 0, max: 86_400 }, true),
    target_event_rate: num({ gt: 0, max: 10_000 }, true),
    num_users: num({ min: 2, max: 1_000_000, int: true }, true),
    num_devices: num({ min: 1, int: true }),
    num_cards: num({ min: 1, int: true }),
    num_ips: num({ min: 1, int: true }),
    heavy_tail_alpha: num({ gt: 1 }),
    user_join_rate: num({ min: 0 }),
    user_leave_rate: num({ min: 0 }),
    amount_median: num({ gt: 0 }),
    amount_sigma: num({ gt: 0 }),
    start_ts: z.string().max(40),
  }),
  mix: z.object({
    transaction: num({ min: 0 }),
    ip_login: num({ min: 0 }),
    device_link: num({ min: 0 }),
    card_link: num({ min: 0 }),
  }),
  hubs: z.array(hub).max(200),
  hubDist: z.object({
    enabled: z.boolean(),
    count: num({ min: 0, max: 10_000, int: true }),
    min_size: num({ min: 2, int: true }),
    max_size: num({ min: 2, max: 100_000, int: true }),
    alpha: num({ gt: 0 }),
    categories: z.array(z.string()),
  }),
  drift: z.object({
    enabled: z.boolean(),
    trigger_time_s: num({ min: 0 }),
    new_hub_size: num({ min: 0, int: true }),
    new_hub_kind: z.string(),
    shift_multiplier: num({ gt: 0 }),
  }),
  rings: z.array(ring).max(200),
  random: z.object({
    enabled: z.boolean(),
    rate_per_min: num({ min: 0, max: 600 }),
    types: z.array(z.string()),
    size_min: num({ min: 2, int: true }),
    size_max: num({ min: 2, int: true }),
    evasion_weights: z.record(z.string(), num({ min: 0 })),
    duration_min: num({ gt: 0 }),
    duration_max: num({ gt: 0 }),
  }),
  adaptive: z.object({
    enabled: z.boolean(),
    penalty: num({ gt: 0, max: 1 }),
    respawn_delay_s: num({ gt: 0 }),
    max_rings: num({ min: 1, max: 100, int: true }),
    strategies: z.array(z.string()),
  }),
});

export type ScenarioForm = z.infer<typeof scenarioFormSchema>;

const str = (v: number | string | null | undefined) =>
  v === null || v === undefined ? "" : String(v);
const parse = (s: string): number | undefined => (s.trim() === "" ? undefined : Number(s));

/** Drop keys whose value is undefined (an empty optional field). */
function compact<T extends Record<string, unknown>>(o: T): Partial<T> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as Partial<T>;
}

export function emptyRing(index: number): ScenarioForm["rings"][number] {
  return {
    id: `ring_${index + 1}`,
    type: "shared_device",
    size: "4",
    spawn_time_s: "10",
    evasion: "none",
    shared_attribute: "",
    length: "",
    grow_interval_s: "",
    initial_members: "",
    active_duration_s: "",
    action_interval_s: "",
    mutate_prob: "",
    intensity: "",
  };
}

/**
 * A scenario as either schema variant returns it. The generated types disagree only
 * on the random-ring duration (a [min, max] pair, typed as a tuple or as an array).
 */
type AnyScenario =
  | ScenarioV1
  | ScenarioIn
  | (Omit<ScenarioV1, "random_rings"> & {
      random_rings?:
        | (Omit<NonNullable<ScenarioV1["random_rings"]>, "active_duration_s"> & {
            active_duration_s?: number[] | null;
          })
        | null;
    });

export function fromScenario(s: AnyScenario): ScenarioForm {
  const sim = s.simulation;
  const hd = sim.hub_size_distribution;
  const rr = s.random_rings;
  const ad = s.adaptive_attacker;
  return {
    name: s.name,
    description: s.description ?? "",
    version: s.version ?? "",
    sim: {
      duration_seconds: str(sim.duration_seconds),
      target_event_rate: str(sim.target_event_rate),
      num_users: str(sim.num_users),
      num_devices: str(sim.num_devices),
      num_cards: str(sim.num_cards),
      num_ips: str(sim.num_ips),
      heavy_tail_alpha: str(sim.heavy_tail_alpha),
      user_join_rate: str(sim.user_join_rate),
      user_leave_rate: str(sim.user_leave_rate),
      amount_median: str(sim.amount_median),
      amount_sigma: str(sim.amount_sigma),
      start_ts: sim.start_ts ?? "",
    },
    mix: {
      transaction: str(sim.benign_mix?.transaction),
      ip_login: str(sim.benign_mix?.ip_login),
      device_link: str(sim.benign_mix?.device_link),
      card_link: str(sim.benign_mix?.card_link),
    },
    hubs: Object.entries(sim.hub_distribution ?? {}).map(([name, h]) => ({
      name,
      type: h.type ?? "ip",
      category: h.category ?? "",
      size: str(h.size),
      fill_time_s: str(h.fill_time_s),
      start_time_s: str(h.start_time_s),
    })),
    hubDist: {
      enabled: !!hd,
      count: str(hd?.count),
      min_size: str(hd?.min_size),
      max_size: str(hd?.max_size),
      alpha: str(hd?.alpha),
      categories: hd?.categories ?? [],
    },
    drift: {
      enabled: !!sim.drift,
      trigger_time_s: str(sim.drift?.trigger_time_s),
      new_hub_size: str(sim.drift?.new_hub_size),
      new_hub_kind: sim.drift?.new_hub_kind ?? "",
      shift_multiplier: str(sim.drift?.shift_multiplier),
    },
    rings: (s.rings ?? []).map((r) => ({
      id: r.id,
      type: r.type,
      size: str(r.size),
      spawn_time_s: str(r.spawn_time_s),
      evasion: r.evasion ?? "none",
      shared_attribute: r.shared_attribute ?? "",
      length: str(r.length),
      grow_interval_s: str(r.grow_interval_s),
      initial_members: str(r.initial_members),
      active_duration_s: str(r.active_duration_s),
      action_interval_s: str(r.action_interval_s),
      mutate_prob: str(r.mutate_prob),
      intensity: str(r.intensity),
    })),
    random: {
      enabled: !!rr,
      rate_per_min: str(rr?.rate_per_min),
      types: rr?.types ?? [],
      size_min: str(rr?.size_min),
      size_max: str(rr?.size_max),
      evasion_weights: Object.fromEntries(
        Object.entries(rr?.evasion_weights ?? {}).map(([k, v]) => [k, str(v)]),
      ),
      duration_min: str(rr?.active_duration_s?.[0]),
      duration_max: str(rr?.active_duration_s?.[1]),
    },
    adaptive: {
      enabled: !!ad,
      penalty: str(ad?.penalty),
      respawn_delay_s: str(ad?.respawn_delay_s),
      max_rings: str(ad?.max_rings),
      strategies: ad?.strategies ?? [],
    },
  };
}

export function toScenario(f: ScenarioForm): ScenarioIn {
  const s = f.sim;
  const mix = compact({
    transaction: parse(f.mix.transaction),
    ip_login: parse(f.mix.ip_login),
    device_link: parse(f.mix.device_link),
    card_link: parse(f.mix.card_link),
  });
  const simulation = compact({
    duration_seconds: parse(s.duration_seconds),
    target_event_rate: parse(s.target_event_rate),
    num_users: parse(s.num_users),
    num_devices: parse(s.num_devices),
    num_cards: parse(s.num_cards),
    num_ips: parse(s.num_ips),
    heavy_tail_alpha: parse(s.heavy_tail_alpha),
    user_join_rate: parse(s.user_join_rate),
    user_leave_rate: parse(s.user_leave_rate),
    amount_median: parse(s.amount_median),
    amount_sigma: parse(s.amount_sigma),
    benign_mix: Object.keys(mix).length ? mix : undefined,
    start_ts: s.start_ts || undefined,
    hub_distribution: f.hubs.length
      ? Object.fromEntries(
          f.hubs.map((h) => [
            h.name,
            compact({
              size: parse(h.size),
              type: h.type,
              category: h.category || undefined,
              fill_time_s: parse(h.fill_time_s),
              start_time_s: parse(h.start_time_s),
            }),
          ]),
        )
      : undefined,
    hub_size_distribution: f.hubDist.enabled
      ? compact({
          count: parse(f.hubDist.count),
          min_size: parse(f.hubDist.min_size),
          max_size: parse(f.hubDist.max_size),
          alpha: parse(f.hubDist.alpha),
          categories: f.hubDist.categories.length ? f.hubDist.categories : undefined,
        })
      : undefined,
    drift: f.drift.enabled
      ? compact({
          trigger_time_s: parse(f.drift.trigger_time_s),
          new_hub_size: parse(f.drift.new_hub_size),
          new_hub_kind: f.drift.new_hub_kind || undefined,
          shift_multiplier: parse(f.drift.shift_multiplier),
        })
      : undefined,
  }) as ScenarioIn["simulation"];
  const rings = f.rings.map(
    (r) =>
      compact({
        id: r.id,
        type: r.type,
        size: parse(r.size),
        spawn_time_s: parse(r.spawn_time_s),
        evasion: r.evasion,
        shared_attribute: r.shared_attribute || undefined,
        length: parse(r.length),
        grow_interval_s: parse(r.grow_interval_s),
        initial_members: parse(r.initial_members),
        active_duration_s: parse(r.active_duration_s),
        action_interval_s: parse(r.action_interval_s),
        mutate_prob: parse(r.mutate_prob),
        intensity: parse(r.intensity),
      }) as RingV1,
  );
  const weights = Object.fromEntries(
    Object.entries(f.random.evasion_weights)
      .map(([k, v]) => [k, parse(v)] as const)
      .filter(([, v]) => v !== undefined),
  );
  const dmin = parse(f.random.duration_min);
  const dmax = parse(f.random.duration_max);
  return compact({
    name: f.name,
    description: f.description || undefined,
    version: f.version || undefined,
    simulation,
    rings,
    random_rings: f.random.enabled
      ? compact({
          rate_per_min: parse(f.random.rate_per_min),
          types: f.random.types.length ? f.random.types : undefined,
          size_min: parse(f.random.size_min),
          size_max: parse(f.random.size_max),
          evasion_weights: Object.keys(weights).length ? weights : undefined,
          active_duration_s:
            dmin !== undefined && dmax !== undefined
              ? ([dmin, dmax] as [number, number])
              : undefined,
        })
      : undefined,
    adaptive_attacker: f.adaptive.enabled
      ? compact({
          penalty: parse(f.adaptive.penalty),
          respawn_delay_s: parse(f.adaptive.respawn_delay_s),
          max_rings: parse(f.adaptive.max_rings),
          strategies: f.adaptive.strategies.length ? f.adaptive.strategies : undefined,
        })
      : undefined,
  }) as ScenarioIn;
}

/**
 * Map a server error location (e.g. ["body","simulation","hub_distribution","office","size"])
 * to the form field that holds it, so server errors appear on the right input.
 */
export function formPath(loc: (string | number)[], form: ScenarioForm): string | null {
  const p = loc[0] === "body" ? loc.slice(1) : loc;
  const [top, a, b, c] = p;
  if (top === "simulation") {
    if (a === "hub_distribution" && typeof b === "string") {
      const i = form.hubs.findIndex((h) => h.name === b);
      return i >= 0 && c ? `hubs.${i}.${String(c)}` : "hubs";
    }
    if (a === "hub_size_distribution") return `hubDist.${String(b ?? "count")}`;
    if (a === "drift") return `drift.${String(b ?? "trigger_time_s")}`;
    return typeof a === "string" ? `sim.${a}` : null;
  }
  if (top === "rings" && typeof a === "number") return `rings.${a}.${String(b ?? "id")}`;
  if (top === "random_rings") return `random.${String(a ?? "rate_per_min")}`;
  if (top === "adaptive_attacker") return `adaptive.${String(a ?? "penalty")}`;
  if (top === "name" || top === "description" || top === "version") return top;
  return null;
}
