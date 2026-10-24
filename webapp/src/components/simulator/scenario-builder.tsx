"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, Download, Play, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { type Path, useFieldArray, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { useSessionUser } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiRequestError, csrfToken, toApiError } from "@/lib/api/client";
import {
  emptyRing,
  formPath,
  fromScenario,
  type ScenarioForm,
  scenarioFormSchema,
  toScenario,
} from "@/lib/simulator/scenario-form";

import { CheckField, MultiCheck, NumberField, Section, SelectField, TextField } from "./fields";

function useCatalog() {
  return useQuery({
    queryKey: ["scenarios", "catalog"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/scenarios/catalog");
      if (!data) throw toApiError(error, response);
      return data;
    },
    staleTime: Infinity,
  });
}

export function useScenarioList() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/scenarios");
      if (!data) throw toApiError(error, response);
      return data;
    },
  });
}

async function loadScenario(name: string) {
  const { data, error, response } = await api.GET("/api/v1/scenarios/{name}", {
    params: { path: { name } },
  });
  if (!data) throw toApiError(error, response);
  return data;
}

/**
 * The scenario builder. A preset loads into the form; anything edited is sent
 * inline and validated by the server exactly as the CLI would load it. An
 * unedited preset is started by name, so the run is identical to the CLI's.
 */
export function ScenarioBuilder() {
  const user = useSessionUser();
  const qc = useQueryClient();
  const catalog = useCatalog();
  const list = useScenarioList();
  const [preset, setPreset] = useState<string>("");
  const [hash, setHash] = useState<string | null>(null);
  const [seed, setSeed] = useState("7");
  const [speed, setSpeed] = useState("5");
  const form = useForm<ScenarioForm>({
    resolver: zodResolver(scenarioFormSchema),
    // Errors appear on Validate/Start and clear while typing. Re-validating on blur
    // instead removed error lines on mousedown, shifting the button under the pointer
    // so the first click after a fix was lost.
    mode: "onSubmit",
    reValidateMode: "onChange",
  });
  const hubs = useFieldArray({ control: form.control, name: "hubs" });
  const rings = useFieldArray({ control: form.control, name: "rings" });
  const loaded = useWatch({ control: form.control, name: "name" }) !== undefined;

  const showServerErrors = (err: unknown) => {
    const e = err instanceof ApiRequestError ? err : null;
    const details = (e?.details as { loc: (string | number)[]; msg: string }[] | undefined) ?? [];
    let placed = 0;
    for (const d of details) {
      const path = formPath(d.loc, form.getValues());
      if (path) {
        form.setError(path as Path<ScenarioForm>, { message: d.msg });
        placed++;
      }
    }
    toast.error(placed ? `${placed} field(s) need attention` : (e?.message ?? String(err)));
  };

  const pick = async (name: string) => {
    setPreset(name);
    setHash(null);
    if (!name) return;
    try {
      form.reset(fromScenario(await loadScenario(name)));
    } catch (err) {
      showServerErrors(err);
    }
  };

  const validate = useMutation({
    mutationFn: async (values: ScenarioForm) => {
      const { data, error, response } = await api.POST("/api/v1/scenarios/validate", {
        body: toScenario(values),
      });
      if (!data) throw toApiError(error, response);
      return data;
    },
    onSuccess: (d) => {
      setHash(d.config_hash);
      toast.success(`Valid: about ${d.events_estimate.toLocaleString("en-US")} events`);
    },
    onError: showServerErrors,
  });

  const download = async (values: ScenarioForm) => {
    const res = await fetch("/api/v1/scenarios/yaml", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-csrf-token": await csrfToken(),
      },
      body: JSON.stringify(toScenario(values)),
    });
    if (!res.ok) return showServerErrors(toApiError(await res.json(), res));
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `${values.name}.yaml`,
    });
    a.click();
    URL.revokeObjectURL(url);
  };

  const save = useMutation({
    mutationFn: async (values: ScenarioForm) => {
      const { data, error, response } = await api.PUT("/api/v1/scenarios/custom/{name}", {
        params: { path: { name: values.name } },
        body: toScenario(values),
      });
      if (!data) throw toApiError(error, response);
      return data;
    },
    onSuccess: (d) => {
      toast.success(`Saved as configs/scenarios/custom/${d.name}.yaml`);
      void qc.invalidateQueries({ queryKey: ["scenarios"] });
    },
    onError: showServerErrors,
  });

  const start = useMutation({
    mutationFn: async (values: ScenarioForm) => {
      const common = { seed: Number(seed), speed_multiplier: Number(speed) };
      // An unedited preset starts by name: the run is then identical to `fraudsim` with that preset.
      const body =
        preset && !form.formState.isDirty
          ? { scenario: preset, ...common }
          : { scenario: values.name, config: toScenario(values), ...common };
      const { data, error, response } = await api.POST("/api/v1/runs", { body });
      if (!data) throw toApiError(error, response);
      return data;
    },
    onSuccess: (d) => {
      toast.success(`Run ${d.run_id} started`);
      void qc.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: showServerErrors,
  });

  const types = catalog.data?.ring_types ?? [];
  const evasions = catalog.data?.evasion_modes ?? [];
  const categories = Object.keys(catalog.data?.hub_categories ?? {});
  const kinds = catalog.data?.attribute_kinds ?? ["device", "card", "ip"];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scenario</CardTitle>
        <CardDescription>
          Start from a preset (configs/scenarios) and adjust it. The server validates it exactly as
          the simulator loads YAML.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label htmlFor="preset" className="text-xs">
            Preset
          </Label>
          <select
            id="preset"
            value={preset}
            onChange={(e) => void pick(e.target.value)}
            className="border-input bg-background h-8 w-full rounded-md border px-2 text-sm"
          >
            <option value="">Choose a scenario…</option>
            {(list.data ?? []).map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
                {s.custom ? " (custom)" : ""} · {s.users} users · {s.duration_s} s · {s.rings} rings
              </option>
            ))}
          </select>
        </div>

        {!loaded ? (
          <p className="text-muted-foreground text-sm">Choose a preset to edit it.</p>
        ) : (
          <form
            className="space-y-3"
            aria-label="Scenario builder"
            onSubmit={form.handleSubmit((v) => start.mutate(v))}
            noValidate
          >
            <Section title="General" open>
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField form={form} name="name" label="Name" hint="Lower-case, digits and _" />
                <TextField form={form} name="version" label="Version" />
              </div>
              <TextField form={form} name="description" label="Description" />
            </Section>

            <Section title="Population and stream" open>
              <div className="grid gap-3 sm:grid-cols-3">
                <NumberField form={form} name="sim.duration_seconds" label="Duration (s)" />
                <NumberField form={form} name="sim.target_event_rate" label="Benign events / s" />
                <NumberField form={form} name="sim.num_users" label="Users" />
                <NumberField form={form} name="sim.num_devices" label="Devices" />
                <NumberField form={form} name="sim.num_cards" label="Cards" />
                <NumberField form={form} name="sim.num_ips" label="IPs" />
                <NumberField
                  form={form}
                  name="sim.heavy_tail_alpha"
                  label="Heavy-tail alpha"
                  hint="> 1"
                />
                <NumberField form={form} name="sim.user_join_rate" label="Users joining / s" />
                <NumberField form={form} name="sim.user_leave_rate" label="Users leaving / s" />
                <NumberField form={form} name="sim.amount_median" label="Amount median" />
                <NumberField form={form} name="sim.amount_sigma" label="Amount sigma" />
                <TextField form={form} name="sim.start_ts" label="Start time (ISO)" />
              </div>
              <fieldset className="grid gap-3 sm:grid-cols-4">
                <legend className="mb-1 text-xs font-medium">Benign event mix (weights)</legend>
                <NumberField form={form} name="mix.transaction" label="Transactions" />
                <NumberField form={form} name="mix.ip_login" label="IP logins" />
                <NumberField form={form} name="mix.device_link" label="Device links" />
                <NumberField form={form} name="mix.card_link" label="Card links" />
              </fieldset>
            </Section>

            <Section
              title={`Benign hubs (${hubs.fields.length})`}
              description="Shared devices, cards and IPs used by many honest users"
            >
              {hubs.fields.map((h, i) => (
                <fieldset key={h.id} className="grid gap-2 rounded-md border p-2 sm:grid-cols-6">
                  <legend className="sr-only">Hub {i + 1}</legend>
                  <TextField form={form} name={`hubs.${i}.name`} label="Hub name" />
                  <SelectField
                    form={form}
                    name={`hubs.${i}.type`}
                    label="Kind"
                    options={kinds.map((k) => ({ value: k }))}
                  />
                  <SelectField
                    form={form}
                    name={`hubs.${i}.category`}
                    label="Category"
                    options={[
                      { value: "", label: "guess from name" },
                      ...categories.map((c) => ({ value: c })),
                    ]}
                  />
                  <NumberField form={form} name={`hubs.${i}.size`} label="Size" />
                  <NumberField form={form} name={`hubs.${i}.fill_time_s`} label="Fill time (s)" />
                  <div className="flex items-end gap-1">
                    <NumberField form={form} name={`hubs.${i}.start_time_s`} label="Start (s)" />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove hub ${i + 1}`}
                      onClick={() => hubs.remove(i)}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                </fieldset>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  hubs.append({
                    name: `hub_${hubs.fields.length + 1}`,
                    type: "ip",
                    category: "",
                    size: "20",
                    fill_time_s: "",
                    start_time_s: "",
                  })
                }
              >
                <Plus aria-hidden /> Add hub
              </Button>
            </Section>

            <Section title="Random hubs" description="Heavy-tailed hub sizes">
              <CheckField form={form} name="hubDist.enabled" label="Generate random hubs" />
              <div className="grid gap-3 sm:grid-cols-4">
                <NumberField form={form} name="hubDist.count" label="Count" />
                <NumberField form={form} name="hubDist.min_size" label="Min size" />
                <NumberField form={form} name="hubDist.max_size" label="Max size" />
                <NumberField form={form} name="hubDist.alpha" label="Pareto alpha" />
              </div>
              <MultiCheck
                form={form}
                name="hubDist.categories"
                legend="Categories"
                options={categories}
              />
            </Section>

            <Section title="Drift" description="A mid-run change in benign behaviour">
              <CheckField form={form} name="drift.enabled" label="Add drift" />
              <div className="grid gap-3 sm:grid-cols-4">
                <NumberField form={form} name="drift.trigger_time_s" label="At (s)" />
                <NumberField form={form} name="drift.new_hub_size" label="New hub size" />
                <SelectField
                  form={form}
                  name="drift.new_hub_kind"
                  label="New hub kind"
                  options={[
                    { value: "", label: "default (ip)" },
                    ...kinds.map((k) => ({ value: k })),
                  ]}
                />
                <NumberField form={form} name="drift.shift_multiplier" label="Shift multiplier" />
              </div>
            </Section>

            <Section title={`Fraud rings (${rings.fields.length})`} open>
              {rings.fields.map((r, i) => (
                <fieldset key={r.id} className="space-y-2 rounded-md border p-2">
                  <legend className="px-1 text-xs font-medium">Ring {i + 1}</legend>
                  <div className="grid gap-2 sm:grid-cols-5">
                    <TextField form={form} name={`rings.${i}.id`} label="Id" />
                    <SelectField
                      form={form}
                      name={`rings.${i}.type`}
                      label="Type"
                      options={types.map((t) => ({ value: t }))}
                    />
                    <SelectField
                      form={form}
                      name={`rings.${i}.evasion`}
                      label="Evasion"
                      options={evasions.map((t) => ({ value: t }))}
                    />
                    <NumberField form={form} name={`rings.${i}.size`} label="Size" />
                    <NumberField
                      form={form}
                      name={`rings.${i}.spawn_time_s`}
                      label="Spawn at (s)"
                    />
                  </div>
                  <details>
                    <summary className="text-muted-foreground cursor-pointer text-xs">
                      More settings
                    </summary>
                    <div className="mt-2 grid gap-2 sm:grid-cols-4">
                      <TextField
                        form={form}
                        name={`rings.${i}.shared_attribute`}
                        label="Shared attribute"
                      />
                      <NumberField
                        form={form}
                        name={`rings.${i}.length`}
                        label="Cycle length (3-6)"
                      />
                      <NumberField
                        form={form}
                        name={`rings.${i}.grow_interval_s`}
                        label="Grow interval (s)"
                      />
                      <NumberField
                        form={form}
                        name={`rings.${i}.initial_members`}
                        label="Initial members"
                      />
                      <NumberField
                        form={form}
                        name={`rings.${i}.active_duration_s`}
                        label="Active for (s)"
                      />
                      <NumberField
                        form={form}
                        name={`rings.${i}.action_interval_s`}
                        label="Action interval (s)"
                      />
                      <NumberField
                        form={form}
                        name={`rings.${i}.mutate_prob`}
                        label="Mutate probability"
                      />
                      <NumberField form={form} name={`rings.${i}.intensity`} label="Intensity" />
                    </div>
                  </details>
                  <Button type="button" variant="ghost" size="sm" onClick={() => rings.remove(i)}>
                    <Trash2 aria-hidden /> Remove ring {i + 1}
                  </Button>
                </fieldset>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => rings.append(emptyRing(rings.fields.length))}
              >
                <Plus aria-hidden /> Add ring
              </Button>
            </Section>

            <Section title="Random rings" description="Rings spawned by a Poisson process">
              <CheckField form={form} name="random.enabled" label="Spawn random rings" />
              <div className="grid gap-3 sm:grid-cols-5">
                <NumberField form={form} name="random.rate_per_min" label="Rings / min" />
                <NumberField form={form} name="random.size_min" label="Min size" />
                <NumberField form={form} name="random.size_max" label="Max size" />
                <NumberField form={form} name="random.duration_min" label="Active min (s)" />
                <NumberField form={form} name="random.duration_max" label="Active max (s)" />
              </div>
              <MultiCheck form={form} name="random.types" legend="Ring types" options={types} />
              <fieldset className="grid gap-3 sm:grid-cols-6">
                <legend className="mb-1 text-xs font-medium">Evasion weights</legend>
                {evasions.map((e) => (
                  <NumberField
                    key={e}
                    form={form}
                    name={`random.evasion_weights.${e}` as Path<ScenarioForm>}
                    label={e.replaceAll("_", " ")}
                  />
                ))}
              </fieldset>
            </Section>

            <Section title="Adaptive attacker">
              <CheckField
                form={form}
                name="adaptive.enabled"
                label="Configure the adaptive attacker"
              />
              <div className="grid gap-3 sm:grid-cols-3">
                <NumberField form={form} name="adaptive.penalty" label="Penalty (0-1]" />
                <NumberField
                  form={form}
                  name="adaptive.respawn_delay_s"
                  label="Respawn delay (s)"
                />
                <NumberField form={form} name="adaptive.max_rings" label="Max rings" />
              </div>
              <MultiCheck
                form={form}
                name="adaptive.strategies"
                legend="Strategies"
                options={evasions.filter((e) => e !== "none")}
              />
            </Section>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="seed" className="text-xs">
                  Seed
                </Label>
                <Input
                  id="seed"
                  inputMode="numeric"
                  className="tabular h-8"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="speed" className="text-xs">
                  Speed (simulated s per wall s; 0 = as fast as possible)
                </Label>
                <Input
                  id="speed"
                  inputMode="decimal"
                  className="tabular h-8"
                  value={speed}
                  onChange={(e) => setSpeed(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" disabled={start.isPending}>
                <Play aria-hidden /> Start run
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={form.handleSubmit((v) => validate.mutate(v))}
              >
                <ShieldCheck aria-hidden /> Validate
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={form.handleSubmit((v) => void download(v))}
              >
                <Download aria-hidden /> Save as YAML
              </Button>
              {user.role === "admin" ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={form.handleSubmit((v) => save.mutate(v))}
                >
                  <Save aria-hidden /> Save to custom scenarios
                </Button>
              ) : null}
              {hash ? (
                <span className="text-ok flex items-center gap-1 text-xs" role="status">
                  <CircleCheck className="size-4" aria-hidden /> valid · config hash{" "}
                  <code>{hash}</code>
                </span>
              ) : null}
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
