"use client";

import { LiveGraph } from "./live-graph";
import { RunControls, useCurrentRun } from "./run-controls";
import { ScenarioBuilder } from "./scenario-builder";

export function Simulator() {
  const run = useCurrentRun();
  const active = !!run.data && run.data.status !== "idle" && run.data.status !== "stopped";
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Simulator</h1>
        <p className="text-muted-foreground text-sm">
          Configure a fraud-ring scenario, run it through the detector and watch the graph. Runs are
          simulated data, recorded under <code>runs/live/</code> with their configuration and seed.
        </p>
      </div>
      <div className="grid gap-6 2xl:grid-cols-2">
        <ScenarioBuilder />
        <div className="space-y-6">
          <RunControls />
          <LiveGraph active={active} />
        </div>
      </div>
    </div>
  );
}
