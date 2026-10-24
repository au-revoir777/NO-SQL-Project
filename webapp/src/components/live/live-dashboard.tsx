"use client";

import {
  Activity,
  BellRing,
  CircleCheck,
  CircleDashed,
  CircleX,
  Gauge,
  Network,
  Radar,
  Siren,
  Target,
  Timer,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { StreamState } from "@/lib/live/use-event-stream";
import { type RunMetrics, useLiveRun, windowedRate } from "@/lib/live/use-live-run";
import { cn } from "@/lib/utils";

import { AlertFeed } from "./alert-feed";
import { KpiCard, type KpiState } from "./kpi-card";
import { LineChart } from "./line-chart";

const n0 = (x: number) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });
const n1 = (x: number) => x.toLocaleString("en-US", { maximumFractionDigits: 1 });
const pct = (x: number | null | undefined) =>
  x === null || x === undefined ? "n/a" : x.toFixed(2);

function StreamBadge({ name, state }: { name: string; state: StreamState }) {
  const map = {
    open: { Icon: CircleCheck, text: "live", tone: "text-ok" },
    connecting: { Icon: CircleDashed, text: "connecting", tone: "text-muted-foreground" },
    reconnecting: { Icon: CircleX, text: "reconnecting", tone: "text-warn" },
    closed: { Icon: CircleX, text: "closed", tone: "text-muted-foreground" },
  }[state];
  return (
    <span role="status" className={cn("flex items-center gap-1 text-xs font-medium", map.tone)}>
      <map.Icon className="size-3.5" aria-hidden />
      {name}: {map.text}
    </span>
  );
}

/** The KPI's state: loading until the stream opens, empty until the run has samples. */
function kpi(
  state: StreamState,
  latest: RunMetrics | null,
  value: (m: RunMetrics) => KpiState,
): KpiState {
  if (latest) return value(latest);
  if (state === "connecting") return { kind: "loading" };
  if (state === "reconnecting") return { kind: "error", message: "Stream interrupted, retrying" };
  return { kind: "empty", message: "No live run yet" };
}

export function LiveDashboard() {
  const live = useLiveRun();
  const [oracle, setOracle] = useState(false);
  const { latest, samples, metricsState } = live;
  const rates = windowedRate(samples);
  const trend = (f: (m: RunMetrics) => number | null | undefined) =>
    samples.map(f).filter((v): v is number => typeof v === "number");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            {latest ? (
              <>
                Run <span className="font-mono">{latest.run_id}</span> · {latest.scenario} · seed{" "}
                {latest.seed} · <Badge variant="outline">{latest.status}</Badge> · simulated{" "}
                <span className="tabular">{n1(latest.sim_time_s)}</span> s
              </>
            ) : (
              "Waiting for a live run. Start one from the live dashboard at /ui or the API; the Simulator page arrives in P4."
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StreamBadge name="KPIs" state={metricsState} />
          <StreamBadge name="Alerts" state={live.alertsState} />
          <Button
            variant={oracle ? "default" : "outline"}
            size="sm"
            aria-pressed={oracle}
            onClick={() => setOracle((o) => !o)}
          >
            <Target aria-hidden />
            Oracle (simulator ground truth)
          </Button>
        </div>
      </header>

      <section aria-label="Key indicators" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Events per second"
          description="Since the start, per wall-clock second"
          icon={Activity}
          state={kpi(metricsState, latest, (m) => ({
            kind: "value",
            value: n1(m.events_per_s),
            detail: `${n0(m.events_total)} events in ${n0(m.batches)} batches`,
            trend: rates.filter((v): v is number => v !== null),
          }))}
        />
        <KpiCard
          title="Graph size"
          description="Users and shared-attribute links"
          icon={Network}
          state={kpi(metricsState, latest, (m) => ({
            kind: "value",
            value: n0(m.graph.users ?? 0),
            detail: `${n0(m.graph.links ?? 0)} links · ${n0(m.graph.transactions ?? 0)} transactions`,
            trend: trend((s) => s.graph.users),
          }))}
        />
        <KpiCard
          title="Open alerts"
          description="Alerted rings not yet dissolved"
          icon={Siren}
          state={kpi(metricsState, latest, (m) => ({
            kind: "value",
            value: n0(m.open_alerts),
            detail: `${n0(m.alerts_total)} alerts in this run`,
            trend: trend((s) => s.open_alerts),
          }))}
        />
        <KpiCard
          title="Alerts per simulated hour"
          description="Scenarios run compressed: not an operational rate"
          icon={BellRing}
          state={kpi(metricsState, latest, (m) =>
            m.alerts_per_sim_hour === null || m.alerts_per_sim_hour === undefined
              ? { kind: "empty", message: "Not enough simulated time yet" }
              : {
                  kind: "value",
                  value: n1(m.alerts_per_sim_hour),
                  trend: trend((s) => s.alerts_per_sim_hour),
                },
          )}
        />
        <KpiCard
          title="Rings tracked"
          description="By status, this run"
          icon={Radar}
          state={kpi(metricsState, latest, (m) => ({
            kind: "value",
            value: n0(m.rings_by_status.candidate + m.rings_by_status.confirmed),
            detail: `${m.rings_by_status.candidate} candidate · ${m.rings_by_status.confirmed} confirmed · ${m.rings_by_status.dissolved} dissolved`,
            trend: trend((s) => s.rings_by_status.candidate + s.rings_by_status.confirmed),
          }))}
        />
        <KpiCard
          title="Detect latency p50"
          description="Per batch, all batches of the run"
          icon={Timer}
          state={kpi(metricsState, latest, (m) =>
            m.detect_ms.p50 === null
              ? { kind: "empty", message: "No batch processed yet" }
              : {
                  kind: "value",
                  value: `${n1(m.detect_ms.p50)} ms`,
                  detail: `p95 ${n1(m.detect_ms.p95 ?? 0)} ms · p99 ${n1(m.detect_ms.p99 ?? 0)} ms · ${m.detect_ms.count} batches`,
                  trend: trend((s) => s.detect_ms.p50),
                },
          )}
        />
        {oracle ? (
          <>
            <KpiCard
              title="Ring F1 (Oracle)"
              description="Oracle (simulator ground truth)"
              icon={Target}
              state={kpi(metricsState, latest, (m) =>
                m.oracle
                  ? {
                      kind: "value",
                      value: pct(m.oracle.ring_f1),
                      detail: `precision ${pct(m.oracle.ring_precision)} · recall ${pct(m.oracle.ring_recall)}`,
                      trend: trend((s) => s.oracle?.ring_f1),
                    }
                  : { kind: "empty", message: "No ground-truth evaluation yet" },
              )}
            />
            <KpiCard
              title="Missed rings (Oracle)"
              description="Oracle (simulator ground truth)"
              icon={Gauge}
              state={kpi(metricsState, latest, (m) =>
                m.oracle && m.oracle.missed_rings !== null && m.oracle.missed_rings !== undefined
                  ? {
                      kind: "value",
                      value: n0(m.oracle.missed_rings),
                      detail: `${m.oracle.rings_detected ?? 0} of ${m.oracle.true_rings ?? 0} true rings detected`,
                    }
                  : { kind: "empty", message: "No ground-truth evaluation yet" },
              )}
            />
          </>
        ) : null}
      </section>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader>
            <CardTitle>Latency and throughput</CardTitle>
            <CardDescription>From the KPI stream of this run</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <LineChart
              title="Detect latency per batch"
              unit="ms"
              x={samples.map((s) => s.sim_time_s)}
              series={[
                {
                  label: "p50",
                  values: samples.map((s) => s.detect_ms.p50),
                  className: "text-primary",
                },
                {
                  label: "p95",
                  values: samples.map((s) => s.detect_ms.p95),
                  className: "text-warn",
                },
                {
                  label: "p99",
                  values: samples.map((s) => s.detect_ms.p99),
                  className: "text-risk-alert",
                },
              ]}
            />
            <LineChart
              title="Throughput"
              unit="events/s"
              x={samples.map((s) => s.sim_time_s)}
              series={[
                {
                  label: "events/s between samples",
                  values: rates,
                  className: "text-ok",
                },
              ]}
            />
          </CardContent>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Alert feed</CardTitle>
            <CardDescription>Alerts and early warnings of this run, newest first</CardDescription>
          </CardHeader>
          <CardContent>
            <AlertFeed alerts={live.alerts} nowSimS={latest?.sim_time_s ?? null} />
          </CardContent>
        </Card>
      </div>

      <div aria-live="polite" className="sr-only">
        {live.fresh.map((a) => (
          <p key={`${a.ring_id}:${a.ts}`}>
            High-risk {a.kind === "alert" ? "alert" : "early warning"}: {a.ring_type} ring of{" "}
            {a.members_count} members, risk {a.risk?.toFixed(2)}.
          </p>
        ))}
      </div>
    </div>
  );
}
