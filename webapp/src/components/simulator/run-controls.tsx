"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Square, Syringe } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useSessionUser } from "@/components/session-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, toApiError } from "@/lib/api/client";

const SPEEDS = [1, 2, 5, 10, 25, 0];

export function useCurrentRun() {
  return useQuery({
    queryKey: ["runs", "current"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/runs/current");
      if (!data) throw toApiError(error, response);
      return data;
    },
    refetchInterval: 1000,
  });
}

const LIVE = new Set(["running", "paused"]);

export function RunControls() {
  const user = useSessionUser();
  const qc = useQueryClient();
  const run = useCurrentRun();
  const live = !!run.data && LIVE.has(run.data.status);
  const [rate, setRate] = useState("");
  const [ringType, setRingType] = useState("shared_ip");
  const [evasion, setEvasion] = useState("hub_hiding");
  const [size, setSize] = useState("4");

  const catalog = useQuery({
    queryKey: ["scenarios", "catalog"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/scenarios/catalog");
      if (!data) throw toApiError(error, response);
      return data;
    },
    staleTime: Infinity,
  });
  const detectors = useQuery({
    queryKey: ["runs", "detectors", run.data?.run_id],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/runs/current/detectors");
      if (!data) throw toApiError(error, response);
      return data;
    },
    enabled: live,
  });

  const act = useMutation({
    mutationFn: async (
      fn: () => Promise<{ data?: unknown; error?: unknown; response: Response }>,
    ) => {
      const { data, error, response } = await fn();
      if (data === undefined) throw toApiError(error, response);
      return data;
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["runs"] }),
    onError: (e) => toast.error(e.message),
  });

  const r = run.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Run</CardTitle>
        <CardDescription>
          {r && r.status !== "idle" ? (
            <>
              <span className="font-mono">{r.run_id}</span> · {r.scenario} · seed {r.seed} ·{" "}
              <Badge variant="outline">{r.status}</Badge> · simulated{" "}
              <span className="tabular">{r.sim_time_s.toFixed(1)}</span> s ·{" "}
              <span className="tabular">{r.events_emitted.toLocaleString("en-US")}</span> events
            </>
          ) : (
            "No run yet. Start one from the scenario on the left."
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {r?.status === "paused" ? (
            <Button
              size="sm"
              onClick={() => act.mutate(() => api.POST("/api/v1/runs/current/resume"))}
            >
              <Play aria-hidden /> Resume
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={r?.status !== "running"}
              onClick={() => act.mutate(() => api.POST("/api/v1/runs/current/pause"))}
            >
              <Pause aria-hidden /> Pause
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={!live}
            onClick={() => act.mutate(() => api.POST("/api/v1/runs/current/stop"))}
          >
            <Square aria-hidden /> Stop
          </Button>
        </div>

        <div role="group" aria-label="Speed" className="flex flex-wrap items-center gap-1">
          <span className="text-muted-foreground mr-1 text-xs">Speed</span>
          {SPEEDS.map((s) => (
            <Button
              key={s}
              size="sm"
              variant={r?.speed_multiplier === s ? "default" : "outline"}
              aria-pressed={r?.speed_multiplier === s}
              disabled={!live}
              onClick={() =>
                act.mutate(() =>
                  api.POST("/api/v1/runs/current/speed", { body: { speed_multiplier: s } }),
                )
              }
            >
              {s === 0 ? "max" : `${s}×`}
            </Button>
          ))}
        </div>

        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            act.mutate(() =>
              api.POST("/api/v1/runs/current/rate", { body: { events_per_second: Number(rate) } }),
            );
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="rate" className="text-xs">
              Benign events per simulated second
            </Label>
            <Input
              id="rate"
              inputMode="decimal"
              className="tabular h-8 w-32"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
            />
          </div>
          <Button size="sm" variant="outline" type="submit" disabled={!live || !rate}>
            Apply
          </Button>
        </form>

        <form
          className="space-y-2"
          aria-label="Inject a ring"
          onSubmit={(e) => {
            e.preventDefault();
            act.mutate(() =>
              api.POST("/api/v1/runs/current/inject", {
                body: {
                  ring_type: ringType as "shared_ip",
                  evasion: evasion as "none",
                  size: Number(size),
                },
              }),
            );
          }}
        >
          <p className="text-xs font-medium">Inject a fraud ring now</p>
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <Label htmlFor="inject-type" className="text-xs">
                Type
              </Label>
              <select
                id="inject-type"
                value={ringType}
                onChange={(e) => setRingType(e.target.value)}
                className="border-input bg-background h-8 rounded-md border px-2 text-sm"
              >
                {(catalog.data?.ring_types ?? []).map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="inject-evasion" className="text-xs">
                Evasion
              </Label>
              <select
                id="inject-evasion"
                value={evasion}
                onChange={(e) => setEvasion(e.target.value)}
                className="border-input bg-background h-8 rounded-md border px-2 text-sm"
              >
                {(catalog.data?.evasion_modes ?? []).map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="inject-size" className="text-xs">
                Size
              </Label>
              <Input
                id="inject-size"
                inputMode="numeric"
                className="tabular h-8 w-16"
                value={size}
                onChange={(e) => setSize(e.target.value)}
              />
            </div>
            <Button size="sm" variant="outline" type="submit" disabled={!live}>
              <Syringe aria-hidden /> Inject
            </Button>
          </div>
        </form>

        <fieldset className="space-y-1">
          <legend className="text-xs font-medium">
            Detectors{user.role !== "admin" ? " (changing them needs the admin role)" : ""}
          </legend>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {(detectors.data ?? []).map((d) => (
              <label key={d.type} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={d.enabled}
                  disabled={!live || user.role !== "admin"}
                  onChange={(e) =>
                    act.mutate(() =>
                      api.PATCH("/api/v1/runs/current/detectors/{detector_type}", {
                        params: { path: { detector_type: d.type } },
                        body: { enabled: e.target.checked },
                      }),
                    )
                  }
                />
                {d.type.replaceAll("_", " ")}
              </label>
            ))}
            {!live ? (
              <span className="text-muted-foreground text-xs">Available while a run is live.</span>
            ) : null}
          </div>
        </fieldset>
      </CardContent>
    </Card>
  );
}
