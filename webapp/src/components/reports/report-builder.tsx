"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FileDown, LoaderCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { errorText } from "@/components/cases/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useCases } from "@/lib/cases/queries";
import {
  DEFAULT_REPORT,
  type ReportValues,
  reportSchema,
  SECTIONS,
  toRequest,
} from "@/lib/reports/form";
import {
  downloadHref,
  type ReportOut,
  useCreateReport,
  useReportableRuns,
} from "@/lib/reports/queries";

function CheckList<T extends string | number>({
  legend,
  items,
  value,
  onChange,
  empty,
}: {
  legend: string;
  items: { value: T; label: string }[];
  value: T[];
  onChange: (v: T[]) => void;
  empty: string;
}) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="text-sm font-medium">{legend}</legend>
      {items.length ? (
        <div className="max-h-44 space-y-1 overflow-y-auto rounded-md border p-2">
          {items.map((it) => (
            <label key={String(it.value)} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={value.includes(it.value)}
                onCheckedChange={(on) =>
                  onChange(on ? [...value, it.value] : value.filter((x) => x !== it.value))
                }
              />
              <span className="truncate">{it.label}</span>
            </label>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">{empty}</p>
      )}
    </fieldset>
  );
}

/**
 * Report builder: scope (runs, cases, alerts and a simulated-time window),
 * sections, the Oracle comparison and the format. The server builds the file.
 */
export function ReportBuilder() {
  const params = useSearchParams();
  const preset = params.get("case");
  const runs = useReportableRuns();
  const cases = useCases([], "", null);
  const create = useCreateReport();
  const [last, setLast] = useState<ReportOut | null>(null);
  const form = useForm<ReportValues>({
    resolver: zodResolver(reportSchema),
    mode: "onSubmit",
    reValidateMode: "onChange",
    defaultValues: {
      ...DEFAULT_REPORT,
      case_ids: preset && Number(preset) > 0 ? [Number(preset)] : [],
      title: preset ? `Case #${preset} investigation report` : "",
    },
  });
  const { errors, isSubmitting } = form.formState;
  const [alertText, setAlertText] = useState("");

  async function onSubmit(v: ReportValues) {
    try {
      const r = await create.mutateAsync(toRequest(v));
      setLast(r);
      toast.success(`Report ready: ${r.rings} ring(s), ${r.format.toUpperCase()}.`);
    } catch (e) {
      form.setError("root", { message: errorText(e, "The report could not be built.") });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>New report</CardTitle>
        <CardDescription>
          Every number comes from the run logs and the case records; each report is hashed and
          audited. Reports are labelled as simulated data, not a regulatory filing.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field data-invalid={errors.title ? true : undefined}>
              <FieldLabel htmlFor="report-title">Title</FieldLabel>
              <Input
                id="report-title"
                aria-invalid={errors.title ? true : undefined}
                {...form.register("title")}
              />
              <FieldError errors={[errors.title]} />
            </Field>
            <div className="grid gap-4 lg:grid-cols-3">
              <Controller
                control={form.control}
                name="run_ids"
                render={({ field }) => (
                  <CheckList
                    legend="Runs"
                    items={(runs.data ?? []).map((r) => ({ value: r.run_id, label: r.label }))}
                    value={field.value}
                    onChange={field.onChange}
                    empty={runs.isPending ? "Loading runs…" : "No recorded runs."}
                  />
                )}
              />
              <Controller
                control={form.control}
                name="case_ids"
                render={({ field }) => (
                  <CheckList
                    legend="Cases"
                    items={(cases.data?.items ?? []).map((c) => ({
                      value: c.id,
                      label: `#${c.id} ${c.title}`,
                    }))}
                    value={field.value}
                    onChange={field.onChange}
                    empty={cases.isPending ? "Loading cases…" : "No cases yet."}
                  />
                )}
              />
              <Field>
                <FieldLabel htmlFor="report-alerts">Alert ids</FieldLabel>
                <Input
                  id="report-alerts"
                  placeholder="e.g. 3, 7, 12"
                  value={alertText}
                  onChange={(e) => {
                    setAlertText(e.target.value);
                    form.setValue(
                      "alert_ids",
                      e.target.value
                        .split(/[,\s]+/)
                        .map(Number)
                        .filter((n) => Number.isInteger(n) && n > 0),
                    );
                  }}
                />
                <FieldDescription>From the alert pages (the number in the URL).</FieldDescription>
              </Field>
            </div>
            {errors.run_ids ? <FieldError>{errors.run_ids.message}</FieldError> : null}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="report-since">
                  Rings first seen from (UTC, simulated)
                </FieldLabel>
                <Input
                  id="report-since"
                  type="datetime-local"
                  step={1}
                  {...form.register("since")}
                />
              </Field>
              <Field data-invalid={errors.until ? true : undefined}>
                <FieldLabel htmlFor="report-until">Until (UTC, simulated)</FieldLabel>
                <Input
                  id="report-until"
                  type="datetime-local"
                  step={1}
                  aria-invalid={errors.until ? true : undefined}
                  {...form.register("until")}
                />
                <FieldError errors={[errors.until]} />
              </Field>
            </div>
            <Controller
              control={form.control}
              name="sections"
              render={({ field }) => (
                <fieldset className="space-y-1.5">
                  <legend className="text-sm font-medium">Sections</legend>
                  <div className="grid gap-1 sm:grid-cols-2">
                    {SECTIONS.map(([key, label]) => (
                      <label key={key} className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={field.value.includes(key)}
                          onCheckedChange={(on) =>
                            field.onChange(
                              on ? [...field.value, key] : field.value.filter((x) => x !== key),
                            )
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                  {errors.sections ? <FieldError>{errors.sections.message}</FieldError> : null}
                </fieldset>
              )}
            />
            <div className="flex flex-wrap items-center gap-6">
              <Controller
                control={form.control}
                name="oracle"
                render={({ field }) => (
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(on) => field.onChange(on === true)}
                    />
                    Add the Oracle (simulator ground truth) comparison
                  </label>
                )}
              />
              <Controller
                control={form.control}
                name="format"
                render={({ field }) => (
                  <fieldset className="flex items-center gap-3 text-sm">
                    <legend className="sr-only">Format</legend>
                    {(["pdf", "html"] as const).map((f) => (
                      <label key={f} className="flex items-center gap-1.5">
                        <input
                          type="radio"
                          name="report-format"
                          value={f}
                          checked={field.value === f}
                          onChange={() => field.onChange(f)}
                          className="accent-primary"
                        />
                        {f.toUpperCase()}
                      </label>
                    ))}
                  </fieldset>
                )}
              />
            </div>
            {errors.root ? <FieldError>{errors.root.message}</FieldError> : null}
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
                Generate report
              </Button>
              {last ? (
                <Button variant="outline" asChild>
                  <a href={downloadHref(last.id)} download>
                    <FileDown aria-hidden /> Download “{last.title}” ({last.format.toUpperCase()})
                  </a>
                </Button>
              ) : null}
            </div>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
