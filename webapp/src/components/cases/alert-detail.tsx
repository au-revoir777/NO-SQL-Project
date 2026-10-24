"use client";

import { ArrowLeft, Info } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { useSessionUser } from "@/components/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { type AlertStatus, NEXT_STATUSES } from "@/lib/cases/filters";
import {
  type AlertDetail as AlertDetailT,
  type LabelKind,
  type LabelResult,
  useAddAlertNote,
  useAlert,
  useLabelAlert,
  useUpdateAlert,
} from "@/lib/cases/queries";

import { AddToCaseDialog, CreateCaseDialog } from "./case-dialogs";
import {
  ActivityList,
  AlertStatusBadge,
  AssigneeSelect,
  errorText,
  fmtTime,
  LABEL_TEXT,
  LabelBadge,
  NotesPanel,
  QueryError,
  RiskBadge,
  userName,
  words,
} from "./common";
import { type Evidence, EvidenceGraph } from "./evidence-graph";

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  );
}

function Overview({ a }: { a: AlertDetailT }) {
  const exp = a.explanation ?? {};
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Risk score">
          <RiskBadge risk={a.risk ?? null} threshold={a.threshold} />
        </Stat>
        <Stat label="Alert threshold">
          <span className="tabular">{a.threshold?.toFixed(2) ?? "–"}</span>
        </Stat>
        <Stat label="Calibration bucket">{a.calibration_bucket || "–"}</Stat>
        <Stat label="Ring status">{words(a.ring_status)}</Stat>
        <Stat label="Ring type">
          <span className="capitalize">{words(a.ring_type)}</span>
        </Stat>
        <Stat label="Members">
          <span className="tabular">{a.members_count}</span>
        </Stat>
        <Stat label="Detectors">{a.detectors.map(words).join(", ") || "–"}</Stat>
        <Stat label="Run">
          <span className="font-mono text-xs">{a.run_id}</span>
        </Stat>
      </dl>
      <Alert>
        <Info aria-hidden />
        <AlertTitle>Read the observed rate with care</AlertTitle>
        <AlertDescription>
          The observed fraud rate comes from the scorer&apos;s calibration on held-out snapshot
          rows. Experiment E10 found that it does not transfer to ring-level alerts: on rings the
          expected calibration error is 0.10, and rings scored 0.8–0.9 were true rings 29% of the
          time (0.9–1.0: 74%). See docs/research/e10_results.md.
        </AlertDescription>
      </Alert>
      <section className="space-y-1">
        <h3 className="text-sm font-semibold">Why it was flagged</h3>
        <p className="text-sm">{String(exp.reason_text ?? a.reason ?? "No reason recorded.")}</p>
      </section>
      <section className="space-y-1">
        <h3 className="text-sm font-semibold">Members</h3>
        <p className="font-mono text-xs break-words">{a.members.join(", ")}</p>
      </section>
    </div>
  );
}

function Contributions({ contrib }: { contrib: Record<string, number> }) {
  const rows = Object.entries(contrib).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1]));
  if (!rows.length)
    return (
      <p className="text-muted-foreground text-sm">
        No contributions: the scorer was not fitted when this ring was scored.
      </p>
    );
  const max = Math.max(...rows.map(([, v]) => Math.abs(v))) || 1;
  return (
    <div className="space-y-2">
      <p className="text-muted-foreground text-sm">
        Contribution of each feature to the raw log-odds of the score. Bars to the right raise the
        risk, bars to the left lower it.
      </p>
      <ul className="space-y-1.5" aria-label="Feature contributions">
        {rows.map(([name, v]) => (
          <li key={name} className="grid grid-cols-[minmax(0,12rem)_1fr_4rem] items-center gap-2">
            <span className="truncate text-sm" title={name}>
              {words(name)}
            </span>
            <span className="relative h-3" aria-hidden>
              <span className="bg-border absolute top-0 left-1/2 h-full w-px" />
              <span
                className={v >= 0 ? "bg-risk-alert absolute h-full" : "bg-ok absolute h-full"}
                style={
                  v >= 0
                    ? { left: "50%", width: `${(Math.abs(v) / max) * 50}%` }
                    : { right: "50%", width: `${(Math.abs(v) / max) * 50}%` }
                }
              />
            </span>
            <span className="tabular text-right text-sm">
              {v >= 0 ? "+" : "−"}
              {Math.abs(v).toFixed(2)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Counterfactuals({ text }: { text: string }) {
  const parts = text
    .split(/(?<=\.)\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!parts.length)
    return <p className="text-muted-foreground text-sm">No counterfactuals for this ring.</p>;
  return (
    <div className="space-y-2">
      <p className="text-muted-foreground text-sm">
        What would have to change for the ring not to be flagged (computed by the scorer).
      </p>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {parts.map((p, i) => (
          <li key={i}>{p}</li>
        ))}
      </ul>
    </div>
  );
}

function Timeline({ a }: { a: AlertDetailT }) {
  return (
    <ol className="divide-y" aria-label="Ring history, newest first">
      {[...(a.history as Record<string, unknown>[])].reverse().map((h, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-x-3 py-2 text-sm">
          <time className="tabular text-muted-foreground text-xs" dateTime={String(h.ts)}>
            {fmtTime(String(h.ts))}
          </time>
          <span className="font-medium">{words(String(h.change))}</span>
          <span className="text-muted-foreground">
            {words(String(h.status ?? ""))} · {String(h.members)} members
            {typeof h.score === "number" ? ` · score ${h.score.toFixed(2)}` : ""}
          </span>
        </li>
      ))}
    </ol>
  );
}

function LabelControls({ a }: { a: AlertDetailT }) {
  const label = useLabelAlert(a.id);
  const [note, setNote] = useState("");
  const [last, setLast] = useState<LabelResult | null>(null);

  async function apply(kind: LabelKind) {
    try {
      const r = await label.mutateAsync({ label: kind, note });
      setLast(r);
      setNote("");
      toast.success(`${LABEL_TEXT[kind]}. ${r.message}`);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  const ad = last?.threshold_adaptation as Record<string, unknown> | null | undefined;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm">Current label:</span>
        <LabelBadge label={a.latest_label} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="label-note">Reason (optional, stored with the label)</Label>
        <Textarea id="label-note" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="flex flex-wrap gap-2">
        {(Object.keys(LABEL_TEXT) as LabelKind[]).map((k) => (
          <Button
            key={k}
            variant={k === "confirmed_fraud" ? "default" : "outline"}
            onClick={() => void apply(k)}
            disabled={label.isPending}
          >
            {LABEL_TEXT[k]}
          </Button>
        ))}
      </div>
      {last ? (
        <Alert>
          <Info aria-hidden />
          <AlertTitle>{last.message}</AlertTitle>
          {ad ? (
            <AlertDescription>
              <p>
                Threshold for {words(String(ad.ring_type ?? a.ring_type))}:{" "}
                <span className="tabular">
                  {Number(ad.threshold_before).toFixed(3)} → {Number(ad.threshold_after).toFixed(3)}
                </span>{" "}
                (action {String(ad.action)}, score {Number(ad.score).toFixed(3)})
              </p>
            </AlertDescription>
          ) : null}
        </Alert>
      ) : null}
      {a.labels.length ? (
        <ul className="text-muted-foreground space-y-1 text-xs" aria-label="Label history">
          {a.labels
            .slice()
            .reverse()
            .map((l) => (
              <li key={l.id}>
                {LABEL_TEXT[l.label]} by {userName(l.author)} · {fmtTime(l.created_at)}
              </li>
            ))}
        </ul>
      ) : null}
    </div>
  );
}

function Triage({ a }: { a: AlertDetailT }) {
  const me = useSessionUser();
  const update = useUpdateAlert(a.id);
  const targets: AlertStatus[] =
    a.status === "closed" && me.role === "admin" ? ["triaged"] : NEXT_STATUSES[a.status];

  async function patch(body: Parameters<typeof update.mutateAsync>[0], what: string) {
    try {
      await update.mutateAsync(body);
      toast.success(what);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <Label htmlFor="alert-status">Status</Label>
        <Select
          value=""
          onValueChange={(v) => void patch({ status: v as AlertStatus }, `Status set to ${v}.`)}
          disabled={!targets.length || update.isPending}
        >
          <SelectTrigger id="alert-status" className="w-44">
            <SelectValue placeholder={targets.length ? "Move to…" : "No further status"} />
          </SelectTrigger>
          <SelectContent>
            {targets.map((s) => (
              <SelectItem key={s} value={s}>
                {s === "triaged" && a.status === "closed" ? "reopen (triaged)" : s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="alert-assignee">Assignee</Label>
        <AssigneeSelect
          id="alert-assignee"
          label="Assignee"
          value={a.assignee?.id ?? null}
          disabled={update.isPending}
          onChange={(id) => void patch({ assignee_id: id }, "Assignee updated.")}
        />
      </div>
      {a.assignee?.id !== me.id ? (
        <Button
          variant="outline"
          onClick={() => void patch({ assignee_id: me.id }, "Assigned to you.")}
          disabled={update.isPending}
        >
          Assign to me
        </Button>
      ) : null}
      <CreateCaseDialog
        alertIds={[a.id]}
        defaultTitle={`${words(a.ring_type)} ring ${a.alert_ref}`}
      />
      <AddToCaseDialog alertIds={[a.id]} />
    </div>
  );
}

export function AlertDetail({ id }: { id: number }) {
  const me = useSessionUser();
  const q = useAlert(id);
  const addNote = useAddAlertNote(id);

  if (q.isPending)
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Loading alert">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  if (q.error)
    return (
      <QueryError
        error={q.error}
        title="Could not load the alert"
        onRetry={() => void q.refetch()}
      />
    );

  const a = q.data;
  const exp = (a.explanation ?? {}) as Record<string, unknown>;
  const evidence = exp.evidence_subgraph as Evidence | undefined;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/alerts">
            <ArrowLeft aria-hidden /> Alerts
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {a.kind === "early_warning" ? "Early warning" : "Alert"}{" "}
            <span className="font-mono">{a.alert_ref}</span>
          </h1>
          <AlertStatusBadge status={a.status} />
          <RiskBadge risk={a.risk ?? null} threshold={a.threshold} />
          {a.live ? (
            <Badge variant="outline" className="border-ok text-ok">
              current run: evidence from the engine
            </Badge>
          ) : null}
          {(a.case_ids ?? []).map((c) => (
            <Badge key={c} variant="outline" asChild>
              <Link href={`/cases/${c}`}>Case #{c}</Link>
            </Badge>
          ))}
        </div>
        <p className="text-muted-foreground text-sm">
          First seen {fmtTime(a.first_seen_at)} · last seen {fmtTime(a.last_seen_at)} · assigned to{" "}
          {userName(a.assignee)}
        </p>
      </div>

      <Card>
        <CardContent>
          <Triage a={a} />
        </CardContent>
      </Card>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="contributions">Contributions</TabsTrigger>
          <TabsTrigger value="counterfactuals">Counterfactuals</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>
        <Card className="mt-2">
          <CardContent>
            <TabsContent value="overview">
              <Overview a={a} />
            </TabsContent>
            <TabsContent value="evidence">
              {evidence?.nodes?.length ? (
                <EvidenceGraph evidence={evidence} />
              ) : (
                <p className="text-muted-foreground text-sm">No evidence subgraph was recorded.</p>
              )}
            </TabsContent>
            <TabsContent value="contributions">
              <Contributions
                contrib={(exp.feature_contributions as Record<string, number> | undefined) ?? {}}
              />
            </TabsContent>
            <TabsContent value="counterfactuals">
              <Counterfactuals text={String(exp.counterfactual ?? "")} />
            </TabsContent>
            <TabsContent value="timeline">
              <Timeline a={a} />
            </TabsContent>
            <TabsContent value="activity" className="grid gap-6 lg:grid-cols-2">
              <section className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Label</CardTitle>
                    <CardDescription>
                      Confirm or dismiss feeds the live run&apos;s alert policy.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <LabelControls a={a} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>History</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ActivityList entries={a.activity ?? []} />
                  </CardContent>
                </Card>
              </section>
              <Card>
                <CardHeader>
                  <CardTitle>Notes</CardTitle>
                </CardHeader>
                <CardContent>
                  <NotesPanel
                    notes={a.notes}
                    meId={me.id}
                    isAdmin={me.role === "admin"}
                    onAdd={(b) => addNote.mutateAsync(b)}
                    adding={addNote.isPending}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </CardContent>
        </Card>
      </Tabs>
    </div>
  );
}
