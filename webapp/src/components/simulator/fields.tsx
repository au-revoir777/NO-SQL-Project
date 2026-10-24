"use client";

import type { ReactNode } from "react";
import { type FieldPath, type UseFormReturn, useController } from "react-hook-form";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ScenarioForm } from "@/lib/simulator/scenario-form";
import { cn } from "@/lib/utils";

type Form = UseFormReturn<ScenarioForm>;
type Name = FieldPath<ScenarioForm>;

const id = (name: string) => `f-${name.replaceAll(".", "-")}`;

function errorOf(form: Form, name: Name): string | undefined {
  const parts = name.split(".");
  let node: unknown = form.formState.errors;
  for (const p of parts) node = (node as Record<string, unknown> | undefined)?.[p];
  return (node as { message?: string } | undefined)?.message;
}

function Shell({
  form,
  name,
  label,
  hint,
  children,
}: {
  form: Form;
  name: Name;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  const err = errorOf(form, name);
  return (
    <div className="space-y-1">
      <Label htmlFor={id(name)} className="text-xs">
        {label}
      </Label>
      {children}
      {err ? (
        <p id={`${id(name)}-err`} className="text-risk-alert text-xs" role="alert">
          {err}
        </p>
      ) : hint ? (
        <p id={`${id(name)}-hint`} className="text-muted-foreground text-xs">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** A text box that holds a number as text (empty = not set). */
export function NumberField(props: {
  form: Form;
  name: Name;
  label: string;
  hint?: string;
  placeholder?: string;
}) {
  const { form, name, placeholder } = props;
  const err = errorOf(form, name);
  return (
    <Shell {...props}>
      <Input
        id={id(name)}
        inputMode="decimal"
        placeholder={placeholder ?? "default"}
        aria-invalid={err ? true : undefined}
        aria-describedby={err ? `${id(name)}-err` : props.hint ? `${id(name)}-hint` : undefined}
        className="tabular h-8"
        {...form.register(name)}
      />
    </Shell>
  );
}

export function TextField(props: { form: Form; name: Name; label: string; hint?: string }) {
  const { form, name } = props;
  const err = errorOf(form, name);
  return (
    <Shell {...props}>
      <Input
        id={id(name)}
        aria-invalid={err ? true : undefined}
        aria-describedby={err ? `${id(name)}-err` : props.hint ? `${id(name)}-hint` : undefined}
        className="h-8"
        {...form.register(name)}
      />
    </Shell>
  );
}

export function SelectField(props: {
  form: Form;
  name: Name;
  label: string;
  options: { value: string; label?: string }[];
  hint?: string;
}) {
  const { form, name, options } = props;
  return (
    <Shell {...props}>
      <select
        id={id(name)}
        className="border-input bg-background focus-visible:ring-ring h-8 w-full rounded-md border px-2 text-sm outline-none focus-visible:ring-2"
        {...form.register(name)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label ?? o.value}
          </option>
        ))}
      </select>
    </Shell>
  );
}

export function CheckField({ form, name, label }: { form: Form; name: Name; label: string }) {
  return (
    <label className="flex items-center gap-2 text-sm" htmlFor={id(name)}>
      <input id={id(name)} type="checkbox" className="size-4" {...form.register(name)} />
      {label}
    </label>
  );
}

/** Several checkboxes writing one string array. */
export function MultiCheck({
  form,
  name,
  legend,
  options,
}: {
  form: Form;
  name: Name;
  legend: string;
  options: string[];
}) {
  const { field } = useController({ control: form.control, name });
  const value = (field.value as string[] | undefined) ?? [];
  return (
    <fieldset className="space-y-1">
      <legend className="text-xs font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {options.map((o) => (
          <label key={o} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              className="size-4"
              checked={value.includes(o)}
              onChange={(e) =>
                field.onChange(e.target.checked ? [...value, o] : value.filter((v) => v !== o))
              }
            />
            {o.replaceAll("_", " ")}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function Section({
  title,
  description,
  children,
  open = false,
  className,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  open?: boolean;
  className?: string;
}) {
  return (
    <details open={open} className={cn("group rounded-lg border p-3", className)}>
      <summary className="cursor-pointer text-sm font-medium select-none">
        {title}
        {description ? (
          <span className="text-muted-foreground ml-2 text-xs font-normal">{description}</span>
        ) : null}
      </summary>
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  );
}
