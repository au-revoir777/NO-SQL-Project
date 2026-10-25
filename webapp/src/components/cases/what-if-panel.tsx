"use client";

import { useMutation } from "@tanstack/react-query";
import { RotateCcw, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, toApiError } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/utils";

import { errorText } from "./common";

type WhatIfOut = components["schemas"]["WhatIfOut"];
type Feature = WhatIfOut["features"][number];

/** Shares in [0, 1]; the other actionable features are counts or log scales. */
const FRACTIONS = new Set([
  "density",
  "near_threshold_frac",
  "account_age_similarity",
  "temporal_burstiness",
]);

export function sliderRange(f: Pick<Feature, "name" | "original">): {
  max: number;
  step: number;
} {
  if (FRACTIONS.has(f.name)) return { max: 1, step: 0.01 };
  if (f.name === "size") return { max: Math.max(10, Math.ceil(f.original * 2)), step: 1 };
  return { max: Math.max(1, Math.ceil(f.original * 2 * 10) / 10), step: 0.01 };
}

function ScoreBar({ score, threshold }: { score: number; threshold: number }) {
  return (
    <div className="space-y-1">
      <div className="bg-muted relative h-3 w-full overflow-hidden rounded-full" aria-hidden>
        <div
          className={cn("h-full", score >= threshold ? "bg-risk-alert" : "bg-ok")}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
        <div
          className="bg-foreground absolute top-0 h-full w-0.5"
          style={{ left: `${threshold * 100}%` }}
        />
      </div>
      <p className="text-muted-foreground text-xs">
        The line marks the alert threshold ({threshold.toFixed(2)}).
      </p>
    </div>
  );
}

/**
 * Interactive what-if: move the actionable features and see the deployed
 * scorer's calibrated score, the decision, and which counterfactual flips it.
 * Nothing is stored.
 */
export function WhatIfPanel({ alertId }: { alertId: number }) {
  const [changes, setChanges] = useState<Record<string, number>>({});
  const [base, setBase] = useState<WhatIfOut | null>(null);
  const run = useMutation({
    mutationFn: async (c: Record<string, number>) => {
      const { data, error, response } = await api.POST("/api/v1/alerts/{alert_id}/what-if", {
        params: { path: { alert_id: alertId } },
        body: { changes: c },
      });
      if (!data) throw toApiError(error, response);
      return data;
    },
  });
  const { mutate } = run;

  // Score once unmodified, then (debounced) after every change.
  useEffect(() => {
    const t = setTimeout(
      () =>
        mutate(changes, {
          onSuccess: (d) => {
            if (!Object.keys(changes).length) setBase(d);
          },
        }),
      Object.keys(changes).length ? 200 : 0,
    );
    return () => clearTimeout(t);
  }, [changes, mutate]);

  const out = run.data ?? base;
  const actionable = useMemo(() => (base?.features ?? []).filter((f) => f.actionable), [base]);

  if (run.error && !out)
    return (
      <Alert variant="destructive">
        <AlertTitle>What-if is not available for this alert</AlertTitle>
        <AlertDescription>{errorText(run.error, "The request failed.")}</AlertDescription>
      </Alert>
    );
  if (!out) return <p className="text-muted-foreground text-sm">Scoring…</p>;

  return (
    <div className="space-y-5">
      <div className="space-y-2" aria-live="polite">
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="text-sm">Score with your changes</span>
          <span className="tabular text-2xl font-semibold">{out.score.toFixed(3)}</span>
          <span className="text-muted-foreground tabular text-sm">
            (scored {out.original_score.toFixed(3)})
          </span>
          {out.alert ? (
            <Badge variant="outline" className="border-risk-alert text-risk-alert">
              alert
            </Badge>
          ) : (
            <Badge variant="outline" className="border-ok text-ok">
              below threshold
            </Badge>
          )}
          {out.flips ? <Badge>decision flips</Badge> : null}
        </div>
        <ScoreBar score={out.score} threshold={out.threshold} />
        <p className="text-muted-foreground text-xs">
          Re-scored by {out.model.from_run ? "this run's scorer" : "the shipped scorer"} (
          {out.model.path}). Only actionable features can change; the others keep their scored
          values.
        </p>
      </div>

      {out.counterfactuals.length ? (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Counterfactuals at the current values</h3>
          <ul className="space-y-1.5">
            {out.counterfactuals.map((cf) => (
              <li key={cf.feature} className="flex flex-wrap items-center gap-2 text-sm">
                <span>
                  {cf.label}: {cf.current.toFixed(2)} → {cf.target.toFixed(2)}
                </span>
                <Badge
                  variant="outline"
                  className={cf.valid ? "border-ok text-ok" : "text-muted-foreground"}
                >
                  {cf.valid ? "flips the decision" : "does not flip"}
                </Badge>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setChanges((c) => ({ ...c, [cf.feature]: cf.target }))}
                >
                  <Wand2 aria-hidden /> Apply
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">
          No single actionable change moves this ring across the threshold.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {actionable.map((f) => {
          const { max, step } = sliderRange(f);
          const value = changes[f.name] ?? f.original;
          const id = `whatif-${f.name}`;
          return (
            <div key={f.name} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2">
                <Label htmlFor={id} className="text-sm">
                  {f.label}
                </Label>
                <span className="text-muted-foreground tabular text-xs">
                  scored {f.original.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id={id}
                  type="range"
                  min={0}
                  max={Math.max(max, value)}
                  step={step}
                  value={value}
                  onChange={(e) => setChanges((c) => ({ ...c, [f.name]: Number(e.target.value) }))}
                  className="accent-primary w-full"
                />
                <Input
                  aria-label={`${f.label} value`}
                  type="number"
                  min={0}
                  step={step}
                  value={Number(value.toFixed(4))}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    if (Number.isFinite(v) && v >= 0) setChanges((c) => ({ ...c, [f.name]: v }));
                  }}
                  className="h-8 w-24"
                />
              </div>
            </div>
          );
        })}
      </div>
      <Button
        variant="outline"
        onClick={() => setChanges({})}
        disabled={!Object.keys(changes).length}
      >
        <RotateCcw aria-hidden /> Reset to the scored values
      </Button>
      {run.error ? <p className="text-destructive text-sm">{errorText(run.error)}</p> : null}
    </div>
  );
}
