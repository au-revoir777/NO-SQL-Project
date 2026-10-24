/**
 * Alert-queue filters <-> the query string of GET /api/v1/alerts, and the
 * selection rules of bulk actions. Pure functions (tested in filters.test.ts).
 */

export const ALERT_STATUSES = ["new", "triaged", "escalated", "closed"] as const;
export type AlertStatus = (typeof ALERT_STATUSES)[number];

export interface AlertFilters {
  status: AlertStatus[];
  ring_type: string[];
  detector: string;
  risk_min: string;
  risk_max: string;
  since: string; // datetime-local value, simulated time
  until: string;
  assignee: string; // "" | "me" | "none" | user id
  q: string;
  sort: "risk" | "first_seen" | "last_seen";
  order: "asc" | "desc";
}

export const DEFAULT_FILTERS: AlertFilters = {
  status: ["new", "triaged", "escalated"],
  ring_type: [],
  detector: "",
  risk_min: "",
  risk_max: "",
  since: "",
  until: "",
  assignee: "",
  q: "",
  sort: "risk",
  order: "desc",
};

/** Query parameters for the API; empty filters are left out. */
export function toQuery(f: AlertFilters): Record<string, string | string[] | number> {
  const q: Record<string, string | string[] | number> = { sort: f.sort, order: f.order };
  if (f.status.length) q.status = f.status;
  if (f.ring_type.length) q.ring_type = f.ring_type;
  if (f.detector) q.detector = f.detector;
  const lo = parseRisk(f.risk_min);
  const hi = parseRisk(f.risk_max);
  if (lo !== null) q.risk_min = lo;
  if (hi !== null) q.risk_max = hi;
  if (f.since) q.since = new Date(f.since).toISOString();
  if (f.until) q.until = new Date(f.until).toISOString();
  if (f.assignee) q.assignee = f.assignee;
  if (f.q.trim()) q.q = f.q.trim();
  return q;
}

function parseRisk(s: string): number | null {
  if (s.trim() === "") return null;
  const v = Number(s);
  return Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : null;
}

/** Problems with the filter values, keyed by field (empty when valid). */
export function filterErrors(f: AlertFilters): Partial<Record<keyof AlertFilters, string>> {
  const e: Partial<Record<keyof AlertFilters, string>> = {};
  for (const k of ["risk_min", "risk_max"] as const) {
    const s = f[k].trim();
    if (s && (!Number.isFinite(Number(s)) || Number(s) < 0 || Number(s) > 1))
      e[k] = "Between 0 and 1";
  }
  const lo = parseRisk(f.risk_min);
  const hi = parseRisk(f.risk_max);
  if (!e.risk_min && !e.risk_max && lo !== null && hi !== null && lo > hi)
    e.risk_max = "Must be at least the minimum";
  if (f.since && f.until && new Date(f.since) > new Date(f.until))
    e.until = "Must be after the start";
  return e;
}

/** A saved view's stored filters, filled up with defaults (older views may lack fields). */
export function fromSaved(stored: Record<string, unknown>): AlertFilters {
  return { ...DEFAULT_FILTERS, ...(stored as Partial<AlertFilters>) };
}

/** Toggle one id; with `range` (shift-click) select everything between the anchor and it. */
export function toggleSelection(
  selected: Set<number>,
  ids: number[],
  id: number,
  anchor: number | null,
  range: boolean,
): Set<number> {
  const next = new Set(selected);
  if (range && anchor !== null && ids.includes(anchor)) {
    const i = ids.indexOf(anchor);
    const j = ids.indexOf(id);
    ids.slice(Math.min(i, j), Math.max(i, j) + 1).forEach((x) => next.add(x));
    return next;
  }
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Statuses a bulk "set status" may target from the current selection (any allowed for one). */
export const NEXT_STATUSES: Record<AlertStatus, AlertStatus[]> = {
  new: ["triaged", "escalated", "closed"],
  triaged: ["escalated", "closed"],
  escalated: ["triaged", "closed"],
  closed: [],
};

export function bulkStatusOptions(statuses: AlertStatus[]): AlertStatus[] {
  const out = new Set<AlertStatus>();
  statuses.forEach((s) => NEXT_STATUSES[s].forEach((n) => out.add(n)));
  return ALERT_STATUSES.filter((s) => out.has(s));
}
