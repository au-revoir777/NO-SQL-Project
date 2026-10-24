"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Briefcase, FolderPlus, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type CreateCaseValues, createCaseSchema, PRIORITIES } from "@/lib/cases/forms";
import { useAttachToCase, useCases, useCreateCase } from "@/lib/cases/queries";

import { errorText } from "./common";

/** New case from one or more alerts; opens the case afterwards. */
export function CreateCaseDialog({
  alertIds,
  defaultTitle = "",
  size = "default",
}: {
  alertIds: number[];
  defaultTitle?: string;
  size?: "default" | "sm";
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const create = useCreateCase();
  const form = useForm<CreateCaseValues>({
    resolver: zodResolver(createCaseSchema),
    defaultValues: { title: defaultTitle, priority: "medium" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(v: CreateCaseValues) {
    try {
      const c = await create.mutateAsync({ ...v, alert_ids: alertIds });
      toast.success(`Case #${c.id} created with ${c.alerts_count} alert(s).`);
      setOpen(false);
      router.push(`/cases/${c.id}`);
    } catch (e) {
      form.setError("root", { message: errorText(e, "Could not create the case.") });
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) form.reset({ title: defaultTitle, priority: "medium" });
      }}
    >
      <DialogTrigger asChild>
        <Button size={size} disabled={!alertIds.length}>
          <Briefcase aria-hidden /> Create case
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New case</DialogTitle>
          <DialogDescription>
            {alertIds.length} alert{alertIds.length === 1 ? "" : "s"} will be attached. Each
            attached alert&apos;s evidence is frozen with a SHA-256 hash.
          </DialogDescription>
        </DialogHeader>
        <form id="create-case" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Field data-invalid={errors.title ? true : undefined}>
              <FieldLabel htmlFor="case-title">Title</FieldLabel>
              <Input
                id="case-title"
                autoComplete="off"
                aria-invalid={errors.title ? true : undefined}
                {...form.register("title")}
              />
              <FieldError errors={[errors.title]} />
            </Field>
            <Field>
              <FieldLabel htmlFor="case-priority">Priority</FieldLabel>
              <Controller
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="case-priority" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PRIORITIES.map((p) => (
                        <SelectItem key={p} value={p}>
                          {p}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            {errors.root ? <FieldError>{errors.root.message}</FieldError> : null}
          </FieldGroup>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button type="submit" form="create-case" disabled={isSubmitting}>
            {isSubmitting ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Create case
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Attach alerts to an existing case that is not closed. */
export function AddToCaseDialog({
  alertIds,
  size = "default",
}: {
  alertIds: number[];
  size?: "default" | "sm";
}) {
  const [open, setOpen] = useState(false);
  const [caseId, setCaseId] = useState("");
  const cases = useCases(["open", "in_review", "escalated"], "", null);
  const attach = useAttachToCase();

  async function submit() {
    try {
      const c = await attach.mutateAsync({ caseId: Number(caseId), alertIds });
      toast.success(`Added to case #${c.id} (${c.alerts_count} alerts).`);
      setOpen(false);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  const items = cases.data?.items ?? [];
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size={size} disabled={!alertIds.length}>
          <FolderPlus aria-hidden /> Add to case
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add to case</DialogTitle>
          <DialogDescription>Only cases that are not closed are listed.</DialogDescription>
        </DialogHeader>
        {items.length ? (
          <Field>
            <FieldLabel htmlFor="attach-case">Case</FieldLabel>
            <Select value={caseId} onValueChange={setCaseId}>
              <SelectTrigger id="attach-case" className="w-full">
                <SelectValue placeholder="Choose a case" />
              </SelectTrigger>
              <SelectContent>
                {items.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    #{c.id} {c.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        ) : (
          <p className="text-muted-foreground text-sm">
            {cases.isPending ? "Loading cases…" : "There are no open cases. Create one instead."}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} disabled={!caseId || attach.isPending}>
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
