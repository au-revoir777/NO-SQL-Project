"use client";

import { useCallback, useState } from "react";

import type { components } from "@/lib/api/schema";

import { type StreamEvent, type StreamState, useEventStream } from "./use-event-stream";

export type RunMetrics = components["schemas"]["RunMetricsV1"];
export type LiveAlert = components["schemas"]["AlertV1"];

/** Samples kept for sparklines and charts (at 2 samples/s: the last 5 minutes). */
export const MAX_SAMPLES = 600;
export const MAX_ALERTS = 200;
/** Alerts at or above this risk are announced to screen readers. */
export const HIGH_RISK = 0.8;

export interface LiveRunState {
  runId: string | null;
  samples: RunMetrics[];
  latest: RunMetrics | null;
  alerts: LiveAlert[];
  /** Alerts that arrived in the last flush, for the aria-live announcement. */
  fresh: LiveAlert[];
  metricsState: StreamState;
  alertsState: StreamState;
}

/**
 * The current run as seen through the SSE streams. Both streams start from the
 * backlog ("0-0"), and everything is keyed on the newest run id: when a new run
 * starts, the state is reset, so every number on the page belongs to the run id
 * shown in the header.
 */
export function useLiveRun(): LiveRunState {
  const [runId, setRunId] = useState<string | null>(null);
  const [samples, setSamples] = useState<RunMetrics[]>([]);
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [fresh, setFresh] = useState<LiveAlert[]>([]);
  const [pending, setPending] = useState<LiveAlert[]>([]); // alerts seen before their run's first sample

  const onMetrics = useCallback(
    (events: StreamEvent<RunMetrics>[]) => {
      const last = events.at(-1);
      if (!last) return;
      const newest = last.data.run_id;
      const mine = events.filter((e) => e.data.run_id === newest).map((e) => e.data);
      if (newest !== runId) {
        setRunId(newest);
        setSamples(mine.slice(-MAX_SAMPLES));
        setAlerts(pending.filter((a) => a.run_id === newest).slice(0, MAX_ALERTS));
        setPending([]);
        setFresh([]);
      } else {
        setSamples((s) => [...s, ...mine].slice(-MAX_SAMPLES));
      }
    },
    [runId, pending],
  );

  const onAlerts = useCallback(
    (events: StreamEvent<LiveAlert>[]) => {
      const incoming = events.map((e) => e.data);
      if (runId === null) {
        setPending((p) => [...incoming.reverse(), ...p].slice(0, MAX_ALERTS * 5));
        return;
      }
      const mine = incoming.filter((a) => a.run_id === runId);
      // Alerts of a run newer than the last sample wait for that run's first sample.
      const later = incoming.filter((a) => a.run_id !== runId);
      if (later.length) setPending((p) => [...later.reverse(), ...p].slice(0, MAX_ALERTS * 5));
      if (!mine.length) return;
      setAlerts((a) => [...mine.reverse(), ...a].slice(0, MAX_ALERTS));
      setFresh(mine.filter((a) => (a.risk ?? 0) >= HIGH_RISK));
    },
    [runId],
  );

  const metricsState = useEventStream<RunMetrics>("/api/v1/stream/metrics", "metrics", {
    onEvents: onMetrics,
    since: "0-0",
  });
  const alertsState = useEventStream<LiveAlert>("/api/v1/stream/alerts", "alert", {
    onEvents: onAlerts,
    since: "0-0",
  });

  return {
    runId,
    samples,
    latest: samples.at(-1) ?? null,
    alerts,
    fresh,
    metricsState,
    alertsState,
  };
}

/**
 * Event rate between consecutive samples (Δevents / Δwall seconds); the first
 * sample, and samples with no wall time in between, have no rate (null). Unlike
 * the cumulative `events_per_s`, this is not dominated by the start-up burst.
 */
export function windowedRate(samples: Pick<RunMetrics, "events_total" | "wall_s">[]) {
  return samples.map((s, i) => {
    const prev = samples[i - 1];
    if (!prev) return null;
    const dt = s.wall_s - prev.wall_s;
    return dt > 0 ? (s.events_total - prev.events_total) / dt : null;
  });
}
