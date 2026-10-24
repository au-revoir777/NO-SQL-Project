"use client";

import { Pause, Play, RotateCcw } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  LAYOUT_H,
  LAYOUT_W,
  parseDeepLink,
  SHORT_NAME,
  sortedLogs,
  stateAt,
  type Story,
  type StoryFlag,
} from "@/lib/replay/story";
import { cn } from "@/lib/utils";

const SPEEDS = [1, 2, 4, 8, 16];
const fmt = (x: number | null | undefined, d = 2) =>
  x === null || x === undefined ? "n/a" : Number(x).toFixed(d);
const name = (key: string) => SHORT_NAME[key] ?? key;

const C = {
  fraud: "var(--risk-alert)",
  flag: "var(--risk-confirmed)",
  warn: "var(--warn)",
  benign: "var(--benign)",
  hub: "var(--node-hub)",
  device: "var(--node-device)",
  card: "var(--node-card)",
  ip: "var(--node-ip)",
  line: "var(--border)",
  ink: "var(--foreground)",
  muted: "var(--muted-foreground)",
};

/**
 * The story replay of one run (a port of demo/story.html): every flag appears
 * at the batch where it fired; the answer key (simulator ground truth) is off
 * by default. Deep links: ?t=&det=&key= (and the old #t=… form).
 */
export function ReplayPlayer({
  story,
  layout,
}: {
  story: Story;
  layout: Map<string, { x: number; y: number }>;
}) {
  const M = story.meta;
  const T = story.truth;
  const A = story.approaches;
  const logs = useMemo(() => sortedLogs(story), [story]);
  const router = useRouter();
  const pathname = usePathname();

  const initial = useMemo(
    () =>
      typeof window === "undefined"
        ? {}
        : parseDeepLink(window.location.search, window.location.hash, M.duration_s),
    [M.duration_s],
  );
  const [t, setT] = useState(initial.t ?? 0);
  const [det, setDet] = useState(
    initial.det && logs[initial.det]
      ? initial.det
      : (A.find((a) => a.key === "system")?.key ?? A[0]!.key),
  );
  const [answerKey, setAnswerKey] = useState(initial.key ?? false);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const last = useRef<number | null>(null);

  // Keep the deep link in the address bar (replace, not push).
  useEffect(() => {
    const id = setTimeout(() => {
      const q = new URLSearchParams({ t: t.toFixed(1), det, ...(answerKey ? { key: "1" } : {}) });
      router.replace(`${pathname}?${q.toString()}`, { scroll: false });
    }, 300);
    return () => clearTimeout(id);
  }, [t, det, answerKey, pathname, router]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = (now: number) => {
      setT((cur) => {
        const next =
          last.current === null
            ? cur
            : Math.min(M.duration_s, cur + ((now - last.current) / 1000) * speed);
        if (next >= M.duration_s) setPlaying(false);
        return next;
      });
      last.current = now;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      last.current = null;
    };
  }, [playing, speed, M.duration_s]);

  const st = stateAt(logs[det] ?? [], t);
  const ringOfUser = useMemo(() => {
    const m: Record<string, string> = {};
    T.forEach((r) => r.members.forEach((u) => (m[u] = r.ring_id)));
    return m;
  }, [T]);
  const nodeById = useMemo(() => new Map(story.graph.nodes.map((n) => [n.id, n])), [story]);
  const pairs = useMemo(() => {
    const out = new Map<string, { s: string; t: string; times: number[] }>();
    for (const x of story.graph.transfers ?? []) {
      if (!nodeById.has(x.s) || !nodeById.has(x.t)) continue;
      const k = `${x.s}>${x.t}`;
      const p = out.get(k) ?? { s: x.s, t: x.t, times: [] };
      p.times.push(x.at);
      out.set(k, p);
    }
    return [...out.values()];
  }, [story, nodeById]);
  const latest = st.items.filter((f) => f.kind === "flag").at(-1);

  const nodeFill = (id: string) => {
    const n = nodeById.get(id)!;
    if (n.kind !== "user")
      return { fill: n.hub ? C.hub : (C[n.kind as "device" | "card" | "ip"] ?? C.muted) };
    const isF = st.flagged.has(n.id);
    const isFraud = n.truth !== "benign";
    if (!answerKey) return { fill: isF ? C.flag : C.benign };
    if (isF) return { fill: isFraud ? C.fraud : C.warn };
    if (isFraud) return { fill: "transparent", stroke: C.fraud, strokeWidth: 2 };
    return { fill: C.benign };
  };

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Replay of run {M.run_id}</h1>
        <p className="text-muted-foreground max-w-3xl text-sm">
          {T.length} fraud rings were planted in a stream of {M.events.toLocaleString("en-US")}{" "}
          events ({M.duration_s} simulated seconds). The same events went through each detector
          below; every flag appears at the batch where it actually fired.
        </p>
        <dl className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {[
            ["seed", M.seed],
            ["scenario", M.scenario],
            ["config", M.config_hash],
            ["stream digest", M.stream_digest.slice(0, 16)],
            ["model", M.model ? `${M.model.type} · training ${M.model.training_id}` : "none"],
          ].map(([k, v]) => (
            <div key={String(k)} className="flex gap-1">
              <dt>{k}</dt>
              <dd className="font-mono">{String(v)}</dd>
            </div>
          ))}
        </dl>
      </header>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <Button
            onClick={() => {
              if (t >= M.duration_s) setT(0);
              setPlaying((p) => !p);
            }}
            aria-label={playing ? "Pause" : "Play"}
          >
            {playing ? (
              <Pause aria-hidden />
            ) : t >= M.duration_s ? (
              <RotateCcw aria-hidden />
            ) : (
              <Play aria-hidden />
            )}
            {playing ? "Pause" : t >= M.duration_s ? "Replay" : "Play"}
          </Button>
          <div role="group" aria-label="Speed" className="flex gap-1">
            {SPEEDS.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={s === speed ? "default" : "outline"}
                aria-pressed={s === speed}
                onClick={() => setSpeed(s)}
              >
                {s}×
              </Button>
            ))}
          </div>
          <div role="group" aria-label="Detector" className="flex gap-1">
            {A.map((a) => (
              <Button
                key={a.key}
                size="sm"
                variant={a.key === det ? "default" : "outline"}
                aria-pressed={a.key === det}
                onClick={() => setDet(a.key)}
              >
                {name(a.key)}
              </Button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input
              id="answer-key"
              type="checkbox"
              className="size-4"
              checked={answerKey}
              onChange={(e) => setAnswerKey(e.target.checked)}
            />
            <Label htmlFor="answer-key">Answer key (simulator ground truth)</Label>
          </div>
          <div className="flex min-w-64 flex-1 items-center gap-3">
            <Label htmlFor="scrub" className="sr-only">
              Simulated time
            </Label>
            <input
              id="scrub"
              type="range"
              min={0}
              max={M.duration_s}
              step={0.1}
              value={t}
              onChange={(e) => {
                setPlaying(false);
                setT(Number(e.target.value));
              }}
              className="flex-1"
            />
            <output htmlFor="scrub" className="tabular text-sm" aria-label="Simulated time">
              {t.toFixed(1)} s / {M.duration_s} s
            </output>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>
              {name(det)} · t = {t.toFixed(1)} s
            </CardTitle>
            <CardDescription>
              Users (circles), shared devices, cards and IPs (squares), transfers (arrows).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <svg
              viewBox={`0 0 ${LAYOUT_W} ${LAYOUT_H}`}
              className="h-auto w-full"
              role="img"
              aria-label={`Transaction graph at ${t.toFixed(1)} simulated seconds`}
            >
              <defs>
                <marker
                  id="arr"
                  viewBox="0 0 10 10"
                  refX="15"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto"
                >
                  <path d="M0,0L10,5L0,10z" fill="context-stroke" />
                </marker>
              </defs>
              {story.graph.edges.map((e, i) => {
                const a = layout.get(e.s);
                const b = layout.get(e.t);
                const vis =
                  a &&
                  b &&
                  e.appear_s <= t &&
                  nodeById.get(e.s)!.appear_s <= t &&
                  nodeById.get(e.t)!.appear_s <= t;
                return vis ? (
                  <line
                    key={i}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={C.line}
                    strokeWidth={0.8}
                  />
                ) : null;
              })}
              {pairs.map((p) => {
                let lastT = -1;
                for (const x of p.times) {
                  if (x <= t) lastT = x;
                  else break;
                }
                if (lastT < 0) return null;
                const a = layout.get(p.s)!;
                const b = layout.get(p.t)!;
                const ring = !!ringOfUser[p.s] && ringOfUser[p.s] === ringOfUser[p.t];
                const fresh = t - lastT < 2.5;
                return (
                  <line
                    key={`${p.s}>${p.t}`}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={ring ? C.fraud : C.muted}
                    strokeWidth={fresh ? 2.6 : ring ? 1.4 : 0.6}
                    opacity={fresh ? 1 : ring ? (answerKey ? 0.85 : 0.5) : 0.18}
                    markerEnd={ring || fresh ? "url(#arr)" : undefined}
                  />
                );
              })}
              {story.graph.nodes.map((n) => {
                if (n.appear_s > t) return null;
                const p = layout.get(n.id)!;
                const active = !(n.left_s && n.left_s <= t);
                const style = nodeFill(n.id);
                return (
                  <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={active ? 1 : 0.25}>
                    <title>
                      {n.kind === "user"
                        ? `${n.id}, joined at ${fmt(n.appear_s, 1)} s${answerKey ? `, truth: ${n.truth}` : ""}`
                        : `${n.id} (${n.kind}), ${n.degree ?? 0} users at the end${n.hub ? `, benign hub: ${n.hub_category}` : ""}`}
                    </title>
                    {n.kind === "user" ? (
                      <circle
                        r={6}
                        fill={style.fill}
                        stroke={style.stroke}
                        strokeWidth={style.strokeWidth}
                      />
                    ) : (
                      <rect
                        x={n.hub ? -11 : -7}
                        y={n.hub ? -11 : -7}
                        width={n.hub ? 22 : 14}
                        height={n.hub ? 22 : 14}
                        rx={3}
                        fill={style.fill}
                      />
                    )}
                    {n.hub ? (
                      <text y={-16} textAnchor="middle" fontSize={12} fill={C.ink}>
                        {n.hub} ({n.degree} users)
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </svg>
            <ul
              className="text-muted-foreground mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs"
              aria-label="Legend"
            >
              {(answerKey
                ? [
                    [C.fraud, "fraud, flagged (correct)"],
                    [C.warn, "legitimate, flagged (false alarm)"],
                    ["ring", "fraud, not flagged (missed)"],
                    [C.benign, "legitimate, not flagged"],
                  ]
                : [
                    [C.flag, `flagged by ${name(det)}`],
                    [C.benign, "not flagged"],
                  ]
              ).map(([c, l]) => (
                <li key={l} className="flex items-center gap-1.5">
                  <span
                    className="inline-block size-3 rounded-full"
                    style={c === "ring" ? { border: `2px solid ${C.fraud}` } : { background: c }}
                    aria-hidden
                  />
                  {l}
                </li>
              ))}
              <li className="flex items-center gap-1.5">
                <span
                  className="inline-block size-3 rounded-sm"
                  style={{ background: C.hub }}
                  aria-hidden
                />
                benign hub
              </li>
              <li>→ transfer (bright = just happened)</li>
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Running score</CardTitle>
              <CardDescription>All detectors at t = {t.toFixed(1)} s</CardDescription>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm" aria-label="Running score per detector">
                <thead>
                  <tr className="text-muted-foreground text-xs">
                    <th className="text-left font-medium">Detector</th>
                    <th className="text-right font-medium">Caught</th>
                    <th className="text-right font-medium">False</th>
                  </tr>
                </thead>
                <tbody>
                  {A.map((a) => {
                    const s = stateAt(logs[a.key] ?? [], t);
                    return (
                      <tr
                        key={a.key}
                        data-detector={a.key}
                        className={cn(a.key === det && "font-semibold")}
                      >
                        <td>{name(a.key)}</td>
                        <td className="tabular text-right" data-testid={`caught-${a.key}`}>
                          {s.caught.size}/{T.length}
                        </td>
                        <td className="tabular text-right" data-testid={`false-${a.key}`}>
                          {s.falseFlags}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
          <LatestAlert flag={latest} det={det} answerKey={answerKey} />
          <Card>
            <CardHeader>
              <CardTitle>Flags</CardTitle>
              <CardDescription>{name(det)}, newest first</CardDescription>
            </CardHeader>
            <CardContent>
              <ul
                className="max-h-72 space-y-1 overflow-auto text-sm"
                aria-label={`Flags of ${name(det)}`}
              >
                {st.items.length === 0 ? (
                  <li className="text-muted-foreground">No flags yet.</li>
                ) : null}
                {st.items
                  .slice()
                  .reverse()
                  .slice(0, 40)
                  .map((f) => (
                    <li key={`${f.ring_id}:${f.t_s}:${f.kind}`} className="flex gap-2">
                      <span className="tabular text-muted-foreground w-14 shrink-0">
                        {fmt(f.t_s, 1)} s
                      </span>
                      <span>
                        {f.kind === "early_warning" ? "early warning" : "flag"} {f.ring_id} ·{" "}
                        {f.members.length} users
                        {answerKey ? (
                          f.true_ring ? (
                            <span className="text-ok"> · {f.true_ring}</span>
                          ) : (
                            <span className="text-warn"> · false alarm</span>
                          )
                        ) : null}
                      </span>
                    </li>
                  ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>

      <section aria-labelledby="final-heading" className="space-y-3">
        <h2 id="final-heading" className="text-lg font-semibold">
          End of the run
        </h2>
        <div className="grid gap-4 lg:grid-cols-3">
          {A.map((a) => {
            const caughtIds = new Set(a.caught.map((c) => c.true_ring));
            return (
              <Card key={a.key}>
                <CardHeader>
                  <CardTitle>{a.title}</CardTitle>
                  <CardDescription>{a.subtitle}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <dl className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <dd className="tabular text-xl font-semibold">
                        {caughtIds.size}/{T.length}
                      </dd>
                      <dt className="text-muted-foreground text-xs">rings caught</dt>
                    </div>
                    <div>
                      <dd className="tabular text-xl font-semibold">{a.false_rings}</dd>
                      <dt className="text-muted-foreground text-xs">false rings</dt>
                    </div>
                    <div>
                      <dd className="tabular text-xl font-semibold">{a.benign_users_flagged}</dd>
                      <dt className="text-muted-foreground text-xs">innocent users flagged</dt>
                    </div>
                  </dl>
                  <ul className="space-y-1">
                    {T.map((r) => {
                      const c = a.caught.find((x) => x.true_ring === r.ring_id);
                      return (
                        <li key={r.ring_id} className="flex justify-between gap-2">
                          <span>
                            {r.ring_id}{" "}
                            <span className="text-muted-foreground">
                              · {r.type}
                              {r.evasion !== "none" ? ` · ${r.evasion}` : ""}
                            </span>
                          </span>
                          {c ? (
                            <Badge variant="outline" className="border-ok text-ok">
                              caught at {fmt(c.flagged_s, 0)} s
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="border-risk-alert text-risk-alert">
                              missed
                            </Badge>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                  <p className="text-muted-foreground text-xs">Flag rule: {a.flag_rule}.</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <p className="text-muted-foreground max-w-4xl text-xs">
        Every number on this page was computed from run <code>{M.run_id}</code> (seed {M.seed},
        scenario <code>{M.scenario}</code>, scenario hash <code>{M.scenario_hash}</code>,
        micro-batches of {M.batch_size} events, full-graph rules every {M.full_interval_s} s).{" "}
        {M.match_rule}. The replay is the recorded log of that run, not a re-simulation; it is a
        single demonstration run, not an aggregate result. Reproduce with <code>{M.command}</code>.
      </p>
    </div>
  );
}

function LatestAlert({
  flag,
  det,
  answerKey,
}: {
  flag: StoryFlag | undefined;
  det: string;
  answerKey: boolean;
}) {
  return (
    <Card aria-live="polite">
      <CardHeader>
        <CardTitle>
          {flag ? `Alert at ${fmt(flag.t_s, 1)} s · ${flag.ring_id}` : "Latest alert"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {!flag ? (
          <p className="text-muted-foreground">No alert from {name(det)} yet.</p>
        ) : (
          <>
            {flag.risk !== null && flag.risk !== undefined ? (
              <p>
                <span className="tabular text-risk-alert text-2xl font-semibold">
                  {fmt(flag.risk)}
                </span>{" "}
                <span className="text-muted-foreground text-xs">
                  calibrated risk
                  {flag.explanation?.threshold !== undefined
                    ? ` · threshold ${fmt(flag.explanation.threshold)}`
                    : ""}
                </span>
              </p>
            ) : (
              <p className="text-muted-foreground text-xs">
                {det.startsWith("cap")
                  ? "rule match, found on two consecutive full-graph runs"
                  : "confirmed on two consecutive detections"}
              </p>
            )}
            <p>
              {flag.explanation
                ? flag.explanation.reason
                : `${flag.members.length} users: ${flag.members.join(", ")}`}
            </p>
            {flag.explanation?.counterfactual ? (
              <p className="bg-muted rounded-md p-2 text-xs">
                <b>Counterfactual.</b> {flag.explanation.counterfactual}
              </p>
            ) : null}
            {answerKey ? (
              <p className="text-xs">
                {flag.true_ring ? (
                  <span className="text-ok">
                    Correct: matches {flag.true_ring} (Jaccard {fmt(flag.jaccard)})
                  </span>
                ) : (
                  <span className="text-warn">False alarm: matches no planted ring</span>
                )}
              </p>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
