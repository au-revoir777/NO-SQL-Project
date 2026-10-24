"use client";

import { BellRing, ChevronLeft, ChevronRight, RotateCcw, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
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
import {
  ALERT_STATUSES,
  type AlertFilters,
  type AlertStatus,
  bulkStatusOptions,
  DEFAULT_FILTERS,
  filterErrors,
  fromSaved,
  toggleSelection,
} from "@/lib/cases/filters";
import { savedViewSchema } from "@/lib/cases/forms";
import {
  useAlerts,
  useAssignableUsers,
  useBulkAlerts,
  useDeleteView,
  useSavedViews,
  useSaveView,
} from "@/lib/cases/queries";
import { cn } from "@/lib/utils";

import { AddToCaseDialog, CreateCaseDialog } from "./case-dialogs";
import {
  AlertStatusBadge,
  errorText,
  fmtTime,
  LabelBadge,
  QueryError,
  RiskBadge,
  userName,
  words,
} from "./common";

export const RING_TYPES = [
  "shared_device",
  "shared_card",
  "shared_ip",
  "money_cycle",
  "smurfing_fan_in",
  "smurfing_fan_out",
  "layered_chain",
  "mixed_attribute",
];
export const DETECTORS = [
  "static_cypher",
  "hub_aware",
  "temporal_cycle",
  "smurfing",
  "community",
  "ensemble",
];
const ANY = "__any";

function FilterError({ id, text }: { id: string; text?: string }) {
  return text ? (
    <p id={id} className="text-destructive text-xs">
      {text}
    </p>
  ) : null;
}

function Filters({
  value,
  onChange,
}: {
  value: AlertFilters;
  onChange: (f: AlertFilters) => void;
}) {
  const users = useAssignableUsers();
  const errors = filterErrors(value);
  const set = <K extends keyof AlertFilters>(k: K, v: AlertFilters[K]) =>
    onChange({ ...value, [k]: v });

  return (
    <div className="space-y-3">
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend className="sr-only">Status</legend>
        <span className="text-muted-foreground mr-1 text-sm">Status</span>
        {ALERT_STATUSES.map((s) => {
          const on = value.status.includes(s);
          return (
            <Button
              key={s}
              size="sm"
              variant={on ? "default" : "outline"}
              aria-pressed={on}
              onClick={() =>
                set("status", on ? value.status.filter((x) => x !== s) : [...value.status, s])
              }
            >
              {s}
            </Button>
          );
        })}
      </fieldset>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1">
          <Label htmlFor="f-q">Search</Label>
          <Input
            id="f-q"
            type="search"
            placeholder="Ring id, member or reason"
            value={value.q}
            onChange={(e) => set("q", e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="f-type">Ring type</Label>
          <Select
            value={value.ring_type[0] ?? ANY}
            onValueChange={(v) => set("ring_type", v === ANY ? [] : [v])}
          >
            <SelectTrigger id="f-type" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any type</SelectItem>
              {RING_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {words(t)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="f-detector">Detector</Label>
          <Select
            value={value.detector || ANY}
            onValueChange={(v) => set("detector", v === ANY ? "" : v)}
          >
            <SelectTrigger id="f-detector" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any detector</SelectItem>
              {DETECTORS.map((d) => (
                <SelectItem key={d} value={d}>
                  {words(d)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="f-assignee">Assignee</Label>
          <Select
            value={value.assignee || ANY}
            onValueChange={(v) => set("assignee", v === ANY ? "" : v)}
          >
            <SelectTrigger id="f-assignee" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Anyone</SelectItem>
              <SelectItem value="me">Assigned to me</SelectItem>
              <SelectItem value="none">Unassigned</SelectItem>
              {(users.data ?? []).map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>
                  {userName(u)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="f-risk-min">Risk from</Label>
            <Input
              id="f-risk-min"
              inputMode="decimal"
              placeholder="0"
              value={value.risk_min}
              aria-invalid={errors.risk_min ? true : undefined}
              aria-describedby="f-risk-min-err"
              onChange={(e) => set("risk_min", e.target.value)}
            />
            <FilterError id="f-risk-min-err" text={errors.risk_min} />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="f-risk-max">Risk to</Label>
            <Input
              id="f-risk-max"
              inputMode="decimal"
              placeholder="1"
              value={value.risk_max}
              aria-invalid={errors.risk_max ? true : undefined}
              aria-describedby="f-risk-max-err"
              onChange={(e) => set("risk_max", e.target.value)}
            />
            <FilterError id="f-risk-max-err" text={errors.risk_max} />
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="f-since">First seen from</Label>
          <Input
            id="f-since"
            type="datetime-local"
            value={value.since}
            onChange={(e) => set("since", e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="f-until">Last seen until</Label>
          <Input
            id="f-until"
            type="datetime-local"
            value={value.until}
            aria-invalid={errors.until ? true : undefined}
            aria-describedby="f-until-err"
            onChange={(e) => set("until", e.target.value)}
          />
          <FilterError id="f-until-err" text={errors.until} />
        </div>
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="f-sort">Sort by</Label>
            <Select
              value={value.sort}
              onValueChange={(v) => set("sort", v as AlertFilters["sort"])}
            >
              <SelectTrigger id="f-sort" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="risk">Risk</SelectItem>
                <SelectItem value="first_seen">First seen</SelectItem>
                <SelectItem value="last_seen">Last seen</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="f-order">Order</Label>
            <Select
              value={value.order}
              onValueChange={(v) => set("order", v as AlertFilters["order"])}
            >
              <SelectTrigger id="f-order" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="desc">Descending</SelectItem>
                <SelectItem value="asc">Ascending</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    </div>
  );
}

function SavedViews({
  filters,
  onApply,
}: {
  filters: AlertFilters;
  onApply: (f: AlertFilters) => void;
}) {
  const views = useSavedViews();
  const save = useSaveView();
  const remove = useDeleteView();
  const [current, setCurrent] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);

  async function submit() {
    const parsed = savedViewSchema.safeParse({ name });
    if (!parsed.success) {
      setNameError(parsed.error.issues[0]?.message ?? "Invalid name");
      return;
    }
    try {
      const v = await save.mutateAsync({
        name: parsed.data.name,
        filters: { ...filters } as unknown as Record<string, never>,
      });
      setCurrent(String(v.id));
      setOpen(false);
      toast.success(`Saved view "${v.name}".`);
    } catch (e) {
      setNameError(errorText(e));
    }
  }

  async function del() {
    const v = views.data?.find((x) => String(x.id) === current);
    if (!v) return;
    try {
      await remove.mutateAsync(v.id);
      setCurrent("");
      toast.success(`Deleted view "${v.name}".`);
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="space-y-1">
        <Label htmlFor="saved-view">Saved view</Label>
        <Select
          value={current || ANY}
          onValueChange={(id) => {
            setCurrent(id === ANY ? "" : id);
            const v = views.data?.find((x) => String(x.id) === id);
            if (v) onApply(fromSaved(v.filters));
          }}
        >
          <SelectTrigger id="saved-view" className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>No saved view</SelectItem>
            {(views.data ?? []).map((v) => (
              <SelectItem key={v.id} value={String(v.id)}>
                {v.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          setNameError(null);
          if (o) setName(views.data?.find((x) => String(x.id) === current)?.name ?? "");
        }}
      >
        <DialogTrigger asChild>
          <Button variant="outline">
            <Save aria-hidden /> Save view
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save the current filters</DialogTitle>
            <DialogDescription>
              A view with the same name is replaced. Views are private to you.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
            noValidate
            className="space-y-1"
          >
            <Label htmlFor="view-name">Name</Label>
            <Input
              id="view-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-invalid={nameError ? true : undefined}
              aria-describedby="view-name-err"
            />
            <FilterError id="view-name-err" text={nameError ?? undefined} />
          </form>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void submit()} disabled={save.isPending}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {current ? (
        <Button variant="ghost" onClick={() => void del()} disabled={remove.isPending}>
          <Trash2 aria-hidden /> Delete view
        </Button>
      ) : null}
    </div>
  );
}

function BulkBar({
  ids,
  statuses,
  onDone,
}: {
  ids: number[];
  statuses: AlertStatus[];
  onDone: () => void;
}) {
  const bulk = useBulkAlerts();
  const users = useAssignableUsers();

  async function run(body: Parameters<typeof bulk.mutateAsync>[0], what: string) {
    try {
      const r = await bulk.mutateAsync(body);
      if (r.rejected.length) {
        toast.warning(
          `${what}: ${r.updated.length} updated, ${r.rejected.length} rejected (${String(
            (r.rejected[0] as { message?: string } | undefined)?.message ?? "",
          )}).`,
        );
      } else {
        toast.success(`${what}: ${r.updated.length} updated.`);
      }
      onDone();
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  return (
    <div
      role="region"
      aria-label="Bulk actions"
      className="bg-muted/60 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2"
    >
      <span className="text-sm font-medium">{ids.length} selected</span>
      <Select
        value=""
        onValueChange={(v) => void run({ ids, action: "assign", assignee_id: Number(v) }, "Assign")}
        disabled={bulk.isPending}
      >
        <SelectTrigger size="sm" className="w-44" aria-label="Assign selected alerts">
          <SelectValue placeholder="Assign to…" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="0">Unassigned</SelectItem>
          {(users.data ?? []).map((u) => (
            <SelectItem key={u.id} value={String(u.id)}>
              {userName(u)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value=""
        onValueChange={(v) =>
          void run({ ids, action: "status", status: v as AlertStatus }, "Set status")
        }
        disabled={bulk.isPending || bulkStatusOptions(statuses).length === 0}
      >
        <SelectTrigger size="sm" className="w-40" aria-label="Set status of selected alerts">
          <SelectValue placeholder="Set status…" />
        </SelectTrigger>
        <SelectContent>
          {bulkStatusOptions(statuses).map((s) => (
            <SelectItem key={s} value={s}>
              {s}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <CreateCaseDialog alertIds={ids} size="sm" />
      <AddToCaseDialog alertIds={ids} size="sm" />
      <Button variant="ghost" size="sm" onClick={onDone}>
        Clear selection
      </Button>
    </div>
  );
}

function isTyping(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  return (
    t.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) ||
    t.getAttribute("role") === "combobox" ||
    t.closest("[role=dialog],[role=listbox],[role=menu]") !== null
  );
}

/** The alert queue: filters, saved views, bulk actions and j/k/Enter/x keyboard triage. */
export function AlertQueue() {
  const router = useRouter();
  const [draft, setDraft] = useState<AlertFilters>(DEFAULT_FILTERS);
  const [applied, setApplied] = useState<AlertFilters>(DEFAULT_FILTERS);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [anchor, setAnchor] = useState<number | null>(null);
  const [focus, setFocus] = useState(0);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  // Apply valid filters after a short pause (typing in search should not refetch per key).
  useEffect(() => {
    if (Object.keys(filterErrors(draft)).length) return;
    const t = setTimeout(() => {
      setApplied(draft);
      setCursors([null]);
      setSelected(new Set());
      setFocus(0);
    }, 250);
    return () => clearTimeout(t);
  }, [draft]);

  const cursor = cursors[cursors.length - 1] ?? null;
  const q = useAlerts(applied, cursor);
  const items = useMemo(() => q.data?.items ?? [], [q.data]);
  const ids = items.map((a) => a.id);
  const selectedIds = ids.filter((id) => selected.has(id));
  const pageStart = (cursors.length - 1) * 50;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target) || !items.length) return;
      const n = items.length;
      let next = focus;
      if (e.key === "j") next = Math.min(n - 1, focus + 1);
      else if (e.key === "k") next = Math.max(0, focus - 1);
      else if (e.key === "Enter" && e.target === rowRefs.current[focus]) {
        router.push(`/alerts/${items[focus]?.id}`);
        return;
      } else if (e.key === "x") {
        const id = items[focus]?.id;
        if (id !== undefined) {
          setSelected((s) => toggleSelection(s, ids, id, anchor, false));
          setAnchor(id);
        }
        return;
      } else return;
      e.preventDefault();
      setFocus(next);
      rowRefs.current[next]?.focus();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const allOn = items.length > 0 && selectedIds.length === items.length;
  const someOn = selectedIds.length > 0 && !allOn;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-4">
          <SavedViews
            filters={draft}
            onApply={(f) => {
              setDraft(f);
            }}
          />
          <Filters value={draft} onChange={setDraft} />
          <div className="flex justify-end">
            <Button variant="ghost" size="sm" onClick={() => setDraft(DEFAULT_FILTERS)}>
              <RotateCcw aria-hidden /> Reset filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {selectedIds.length ? (
        <BulkBar
          ids={selectedIds}
          statuses={items.filter((a) => selected.has(a.id)).map((a) => a.status)}
          onDone={() => setSelected(new Set())}
        />
      ) : null}

      <p className="text-muted-foreground text-xs" id="queue-help">
        Keyboard: <kbd>j</kbd>/<kbd>k</kbd> move between alerts, <kbd>Enter</kbd> opens,{" "}
        <kbd>x</kbd> selects. Shift-click a checkbox to select a range.
      </p>

      <Card className="overflow-hidden py-0">
        <CardContent className="px-0">
          {q.isPending ? (
            <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading alerts">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : q.error ? (
            <div className="p-4">
              <QueryError
                error={q.error}
                title="Could not load alerts"
                onRetry={() => void q.refetch()}
              />
            </div>
          ) : items.length === 0 ? (
            <div className="p-4">
              <EmptyState icon={BellRing} title="No alerts match">
                Alerts are recorded while a run is live (start one in the Simulator). Change the
                filters to see closed alerts or other runs.
              </EmptyState>
            </div>
          ) : (
            <Table aria-describedby="queue-help">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      aria-label="Select all alerts on this page"
                      checked={allOn ? true : someOn ? "indeterminate" : false}
                      onCheckedChange={() => setSelected(allOn ? new Set() : new Set(ids))}
                    />
                  </TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Alert</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Members</TableHead>
                  <TableHead>Detectors</TableHead>
                  <TableHead>First seen</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead>Label</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((a, i) => (
                  <TableRow
                    key={a.id}
                    ref={(el) => {
                      rowRefs.current[i] = el;
                    }}
                    tabIndex={i === focus ? 0 : -1}
                    aria-selected={selected.has(a.id)}
                    onFocus={() => setFocus(i)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && e.target === e.currentTarget)
                        router.push(`/alerts/${a.id}`);
                    }}
                    className={cn(
                      "h-11 cursor-pointer outline-none",
                      i === focus &&
                        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-inset",
                    )}
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest("button,a,[role=checkbox]")) return;
                      router.push(`/alerts/${a.id}`);
                    }}
                  >
                    <TableCell>
                      <Checkbox
                        aria-label={`Select alert ${a.alert_ref}`}
                        checked={selected.has(a.id)}
                        onClick={(e) => {
                          e.preventDefault();
                          setSelected((s) => toggleSelection(s, ids, a.id, anchor, e.shiftKey));
                          setAnchor(a.id);
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <RiskBadge risk={a.risk ?? null} threshold={a.threshold} />
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/alerts/${a.id}`}
                        className="font-mono text-xs font-medium underline-offset-4 hover:underline"
                      >
                        {a.alert_ref}
                      </Link>
                      <span className="text-muted-foreground block text-xs">
                        {a.kind === "early_warning" ? "Early warning" : "Alert"}
                        {a.calibration_bucket ? ` · ${a.calibration_bucket.split(" ")[0]}` : ""}
                      </span>
                    </TableCell>
                    <TableCell className="capitalize">{words(a.ring_type)}</TableCell>
                    <TableCell className="tabular text-right">{a.members_count}</TableCell>
                    <TableCell className="text-xs">{a.detectors.map(words).join(", ")}</TableCell>
                    <TableCell className="tabular text-xs">{fmtTime(a.first_seen_at)}</TableCell>
                    <TableCell className="tabular text-xs">{fmtTime(a.last_seen_at)}</TableCell>
                    <TableCell>
                      <AlertStatusBadge status={a.status} />
                    </TableCell>
                    <TableCell className="text-sm">{userName(a.assignee)}</TableCell>
                    <TableCell>
                      <LabelBadge label={a.latest_label} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {q.data && (q.data.total ?? 0) > 0 ? (
        <nav className="flex items-center justify-between gap-2" aria-label="Pages">
          <p className="text-muted-foreground tabular text-sm">
            {pageStart + 1}–{pageStart + items.length} of {q.data.total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={cursors.length < 2}
              onClick={() => {
                setCursors((c) => c.slice(0, -1));
                setFocus(0);
              }}
            >
              <ChevronLeft aria-hidden /> Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!q.data.next_cursor}
              onClick={() => {
                setCursors((c) => [...c, q.data.next_cursor ?? null]);
                setFocus(0);
              }}
            >
              Next <ChevronRight aria-hidden />
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
