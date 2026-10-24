"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, FileLock2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { useSessionUser } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  type CaseStatusValues,
  caseStatusSchema,
  caseTargets,
  PRIORITIES,
} from "@/lib/cases/forms";
import {
  type CaseDetail as CaseDetailT,
  type Priority,
  useAddCaseNote,
  useCase,
  useSnapshot,
  useUpdateCase,
} from "@/lib/cases/queries";

import {
  ActivityList,
  AlertStatusBadge,
  AssigneeSelect,
  CaseStatusBadge,
  errorText,
  fmtTime,
  NotesPanel,
  PriorityBadge,
  QueryError,
  RiskBadge,
  userName,
  words,
} from "./common";

/** Status change; closing asks for a resolution (validated before the request). */
function StatusForm({ c }: { c: CaseDetailT }) {
  const me = useSessionUser();
  const update = useUpdateCase(c.id);
  const targets = caseTargets(c.status, me.role === "admin");
  const form = useForm<CaseStatusValues>({
    resolver: zodResolver(caseStatusSchema),
    defaultValues: { status: targets[0] ?? c.status, resolution: "" },
  });
  const { errors, isSubmitting } = form.formState;
  const closing = useWatch({ control: form.control, name: "status" }) === "closed";

  async function onSubmit(v: CaseStatusValues) {
    try {
      await update.mutateAsync({
        status: v.status,
        ...(v.status === "closed" ? { resolution: v.resolution } : {}),
      });
      toast.success(`Case moved to ${words(v.status)}.`);
      form.reset({
        status: caseTargets(v.status, me.role === "admin")[0] ?? v.status,
        resolution: "",
      });
    } catch (e) {
      form.setError("root", { message: errorText(e) });
    }
  }

  if (!targets.length)
    return (
      <p className="text-muted-foreground text-sm">
        This case is closed. Only an admin can reopen it.
      </p>
    );

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="case-next-status">Move to</FieldLabel>
          <Controller
            control={form.control}
            name="status"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="case-next-status" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {targets.map((s) => (
                    <SelectItem key={s} value={s}>
                      {c.status === "closed" ? `reopen (${words(s)})` : words(s)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
        {closing ? (
          <Field data-invalid={errors.resolution ? true : undefined}>
            <FieldLabel htmlFor="case-resolution">Resolution</FieldLabel>
            <Textarea
              id="case-resolution"
              aria-invalid={errors.resolution ? true : undefined}
              {...form.register("resolution")}
            />
            <FieldError errors={[errors.resolution]} />
          </Field>
        ) : null}
        {errors.root ? <FieldError>{errors.root.message}</FieldError> : null}
        <Button type="submit" disabled={isSubmitting} className="w-fit">
          Update status
        </Button>
      </FieldGroup>
    </form>
  );
}

function SnapshotDialog({
  caseId,
  alertId,
  onClose,
}: {
  caseId: number;
  alertId: number | null;
  onClose: () => void;
}) {
  const snap = useSnapshot(caseId, alertId);
  return (
    <Dialog open={alertId !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Frozen evidence</DialogTitle>
          <DialogDescription>
            The alert&apos;s evidence as it was when attached to this case (canonical JSON).
          </DialogDescription>
        </DialogHeader>
        {snap.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : snap.error ? (
          <p className="text-destructive text-sm">{snap.error.message}</p>
        ) : (
          <div className="space-y-2">
            <p className="font-mono text-xs break-all">SHA-256 {snap.data.sha256}</p>
            <pre className="bg-muted max-h-[50vh] overflow-auto rounded p-3 text-xs">
              {JSON.stringify(snap.data.snapshot, null, 2)}
            </pre>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function CaseDetail({ id }: { id: number }) {
  const me = useSessionUser();
  const q = useCase(id);
  const update = useUpdateCase(id);
  const addNote = useAddCaseNote(id);
  const [snapFor, setSnapFor] = useState<number | null>(null);

  async function patch(body: Parameters<typeof update.mutateAsync>[0], what: string) {
    try {
      await update.mutateAsync(body);
      toast.success(what);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  if (q.isPending)
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Loading case">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  if (q.error)
    return (
      <QueryError
        error={q.error}
        title="Could not load the case"
        onRetry={() => void q.refetch()}
      />
    );

  const c = q.data;
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/cases">
            <ArrowLeft aria-hidden /> Cases
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            Case #{c.id}: {c.title}
          </h1>
          <CaseStatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
        </div>
        <p className="text-muted-foreground text-sm">
          Opened by {userName(c.created_by)} on {fmtTime(c.created_at)} · updated{" "}
          {fmtTime(c.updated_at)}
        </p>
        {c.resolution ? (
          <p className="text-sm">
            <span className="font-medium">Resolution:</span> {c.resolution}
          </p>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent>
            <StatusForm key={c.status} c={c} />
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Owner and priority</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-4">
            <div className="space-y-1">
              <Label htmlFor="case-owner">Assignee</Label>
              <AssigneeSelect
                id="case-owner"
                label="Assignee"
                value={c.assignee?.id ?? null}
                disabled={update.isPending}
                onChange={(uid) => void patch({ assignee_id: uid }, "Assignee updated.")}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="case-prio">Priority</Label>
              <Select
                value={c.priority}
                onValueChange={(v) =>
                  void patch({ priority: v as Priority }, `Priority set to ${v}.`)
                }
                disabled={update.isPending}
              >
                <SelectTrigger id="case-prio" className="w-40">
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
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Attached alerts</CardTitle>
          <CardDescription>
            Each alert&apos;s evidence was frozen when it was attached; the hash identifies that
            copy.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Alert</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Attached</TableHead>
                <TableHead>Evidence hash</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {c.alerts.map((ca) => (
                <TableRow key={ca.alert.id}>
                  <TableCell>
                    <Link
                      href={`/alerts/${ca.alert.id}`}
                      className="font-mono text-xs underline-offset-4 hover:underline"
                    >
                      {ca.alert.alert_ref}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <RiskBadge risk={ca.alert.risk ?? null} threshold={ca.alert.threshold} />
                  </TableCell>
                  <TableCell className="capitalize">{words(ca.alert.ring_type)}</TableCell>
                  <TableCell>
                    <AlertStatusBadge status={ca.alert.status} />
                  </TableCell>
                  <TableCell className="tabular text-xs">{fmtTime(ca.added_at)}</TableCell>
                  <TableCell>
                    {ca.snapshot_sha256 ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="font-mono text-xs"
                        onClick={() => setSnapFor(ca.alert.id)}
                        aria-label={`Show frozen evidence of ${ca.alert.alert_ref}`}
                      >
                        <FileLock2 aria-hidden /> {ca.snapshot_sha256.slice(0, 12)}…
                      </Button>
                    ) : (
                      "–"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <NotesPanel
              notes={c.notes}
              meId={me.id}
              isAdmin={me.role === "admin"}
              onAdd={(b) => addNote.mutateAsync(b)}
              adding={addNote.isPending}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>History</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityList entries={c.history} />
          </CardContent>
        </Card>
      </div>
      <SnapshotDialog caseId={c.id} alertId={snapFor} onClose={() => setSnapFor(null)} />
    </div>
  );
}
