"use client";

import { History, Pencil, RefreshCw, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError } from "@/lib/api/client";
import {
  type CaseStatus,
  type LabelKind,
  type NoteOut,
  type Priority,
  type UserRef,
  useAssignableUsers,
  useEditNote,
} from "@/lib/cases/queries";
import type { AlertStatus } from "@/lib/cases/filters";
import { cn } from "@/lib/utils";

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" });

export function fmtTime(iso: string | null | undefined): string {
  return iso ? dateFmt.format(new Date(iso)) : "–";
}

export function errorText(e: unknown, fallback = "The change could not be saved."): string {
  return e instanceof ApiRequestError ? e.message : fallback;
}

export function words(s: string | null | undefined): string {
  return s ? s.replaceAll("_", " ") : "unknown";
}

export function userName(u: UserRef | null | undefined): string {
  return u ? u.display_name || u.email : "Unassigned";
}

/** Risk as a number; the colour is a cue only, the value is always shown. */
export function RiskBadge({ risk, threshold }: { risk: number | null; threshold?: number | null }) {
  const cls =
    risk === null
      ? "text-muted-foreground"
      : risk >= (threshold ?? 0.8)
        ? "border-risk-alert text-risk-alert"
        : risk >= 0.5
          ? "border-warn text-warn"
          : "text-muted-foreground";
  return (
    <Badge variant="outline" className={cn("tabular", cls)}>
      {risk === null ? "n/a" : risk.toFixed(2)}
    </Badge>
  );
}

const ALERT_STATUS_CLASS: Record<AlertStatus, string> = {
  new: "border-risk-alert text-risk-alert",
  triaged: "border-warn text-warn",
  escalated: "border-primary text-foreground font-semibold",
  closed: "text-muted-foreground",
};

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return (
    <Badge variant="outline" className={ALERT_STATUS_CLASS[status]}>
      {status}
    </Badge>
  );
}

const CASE_STATUS_CLASS: Record<CaseStatus, string> = {
  open: "border-risk-alert text-risk-alert",
  in_review: "border-warn text-warn",
  escalated: "border-primary text-foreground font-semibold",
  closed: "text-muted-foreground",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return (
    <Badge variant="outline" className={CASE_STATUS_CLASS[status]}>
      {words(status)}
    </Badge>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const cls =
    priority === "critical"
      ? "bg-destructive text-white"
      : priority === "high"
        ? "border-risk-alert text-risk-alert"
        : "text-muted-foreground";
  return (
    <Badge variant={priority === "critical" ? "default" : "outline"} className={cls}>
      {priority}
    </Badge>
  );
}

export const LABEL_TEXT: Record<LabelKind, string> = {
  confirmed_fraud: "Confirmed fraud",
  dismissed_benign: "Dismissed (benign)",
  needs_info: "Needs info",
};

export function LabelBadge({ label }: { label: LabelKind | null | undefined }) {
  if (!label) return <span className="text-muted-foreground">–</span>;
  const cls =
    label === "confirmed_fraud"
      ? "border-risk-alert text-risk-alert"
      : label === "dismissed_benign"
        ? "border-ok text-ok"
        : "border-warn text-warn";
  return (
    <Badge variant="outline" className={cls}>
      {LABEL_TEXT[label]}
    </Badge>
  );
}

export function QueryError({
  error,
  title,
  onRetry,
}: {
  error: Error;
  title: string;
  onRetry: () => void;
}) {
  return (
    <Alert variant="destructive">
      <TriangleAlert aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {error instanceof ApiRequestError && error.requestId ? (
          <p className="font-mono text-xs">Request id: {error.requestId}</p>
        ) : null}
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          <RefreshCw aria-hidden /> Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

/** Assignee picker: a user, or "Unassigned" (sent as 0). */
export function AssigneeSelect({
  value,
  onChange,
  disabled,
  label,
  id,
}: {
  value: number | null;
  onChange: (id: number) => void;
  disabled?: boolean;
  label: string;
  id?: string;
}) {
  const users = useAssignableUsers();
  return (
    <Select
      value={value === null ? "0" : String(value)}
      onValueChange={(v) => onChange(Number(v))}
      disabled={disabled || users.isPending}
    >
      <SelectTrigger id={id} className="w-56" aria-label={label}>
        <SelectValue placeholder="Unassigned" />
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
  );
}

/** Note text: plain text with line breaks kept (Markdown is stored as written, not rendered). */
function NoteBody({ body }: { body: string }) {
  return <p className="text-sm break-words whitespace-pre-wrap">{body}</p>;
}

function NoteItem({ note, canEdit }: { note: NoteOut; canEdit: boolean }) {
  const revisions = note.revisions ?? [];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.body);
  const [showRevisions, setShowRevisions] = useState(false);
  const edit = useEditNote();

  async function save() {
    try {
      await edit.mutateAsync({ id: note.id, body: draft.trim() });
      setEditing(false);
      toast.success("Note updated; the earlier version is kept.");
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  return (
    <li className="space-y-1.5 py-3">
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 text-xs">
        <span className="text-foreground font-medium">{userName(note.author)}</span>
        <time dateTime={note.created_at}>{fmtTime(note.created_at)}</time>
        {note.edited ? <span>(edited)</span> : null}
        {canEdit && !editing ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-1.5"
            onClick={() => {
              setDraft(note.body);
              setEditing(true);
            }}
          >
            <Pencil aria-hidden /> Edit
          </Button>
        ) : null}
        {revisions.length ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-1.5"
            aria-expanded={showRevisions}
            onClick={() => setShowRevisions((s) => !s)}
          >
            <History aria-hidden /> {revisions.length} earlier version
            {revisions.length > 1 ? "s" : ""}
          </Button>
        ) : null}
      </div>
      {editing ? (
        <div className="space-y-2">
          <Label htmlFor={`note-edit-${note.id}`} className="sr-only">
            Edit note
          </Label>
          <Textarea
            id={`note-edit-${note.id}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => void save()}
              disabled={!draft.trim() || edit.isPending}
            >
              Save
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <NoteBody body={note.body} />
      )}
      {showRevisions ? (
        <ol className="border-muted space-y-2 border-l-2 pl-3" aria-label="Earlier versions">
          {revisions.map((r, i) => (
            <li key={i} className="text-muted-foreground text-xs">
              <span>
                {userName(r.author as unknown as UserRef | null)} ·{" "}
                {fmtTime(String(r.created_at ?? ""))}
              </span>
              <NoteBody body={String(r.body ?? "")} />
            </li>
          ))}
        </ol>
      ) : null}
    </li>
  );
}

/** Notes with add, edit (author or admin) and the earlier versions of edited notes. */
export function NotesPanel({
  notes,
  meId,
  isAdmin,
  onAdd,
  adding,
}: {
  notes: NoteOut[];
  meId: number;
  isAdmin: boolean;
  onAdd: (body: string) => Promise<unknown>;
  adding: boolean;
}) {
  const [draft, setDraft] = useState("");
  const tooLong = draft.length > 20_000;

  async function add() {
    try {
      await onAdd(draft.trim());
      setDraft("");
      toast.success("Note added.");
    } catch (e) {
      toast.error(errorText(e));
    }
  }

  return (
    <div className="space-y-3">
      {notes.length ? (
        <ul className="divide-y" aria-label="Notes">
          {notes.map((n) => (
            <NoteItem key={n.id} note={n} canEdit={isAdmin || n.author?.id === meId} />
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-sm">No notes yet.</p>
      )}
      <div className="space-y-2">
        <Label htmlFor="new-note">Add a note</Label>
        <Textarea
          id="new-note"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="What did you check, and what did you find?"
          aria-invalid={tooLong || undefined}
          aria-describedby="new-note-help"
        />
        <p
          id="new-note-help"
          className={cn("text-xs", tooLong ? "text-destructive" : "text-muted-foreground")}
        >
          {tooLong
            ? "Notes are limited to 20,000 characters."
            : "Notes are kept with every earlier version and written to the audit trail."}
        </p>
        <Button onClick={() => void add()} disabled={!draft.trim() || tooLong || adding}>
          Add note
        </Button>
      </div>
    </div>
  );
}

const ACTION_TEXT: Record<string, string> = {
  ALERT_STATUS: "changed the status",
  ALERT_ASSIGNED: "changed the assignee",
  ALERT_LABELED: "labelled the alert",
  NOTE_ADDED: "added a note",
  NOTE_EDITED: "edited a note",
  CASE_CREATED: "created the case",
  CASE_UPDATED: "updated the case",
  CASE_ALERT_ATTACHED: "attached an alert",
};

function describe(details: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(details)) {
    if (k === "ip" || v === null || v === undefined || v === "") continue;
    if (typeof v === "object") continue;
    parts.push(`${words(k)}: ${String(v)}`);
  }
  return parts.join(" · ");
}

/** Audit entries about one object, newest first. */
export function ActivityList({ entries }: { entries: Record<string, unknown>[] }) {
  if (!entries.length) return <p className="text-muted-foreground text-sm">No activity yet.</p>;
  return (
    <ol className="divide-y" aria-label="Activity, newest first">
      {[...entries].reverse().map((e) => {
        const action = String(e.action_type);
        return (
          <li key={String(e.seq)} className="space-y-0.5 py-2 text-sm">
            <p>
              <span className="font-medium">{String(e.actor)}</span>{" "}
              {ACTION_TEXT[action] ?? words(action.toLowerCase())}
            </p>
            <p className="text-muted-foreground text-xs">
              <time dateTime={String(e.ts)}>{fmtTime(String(e.ts))}</time>
              {" · "}
              {describe((e.details as Record<string, unknown>) ?? {}) || `#${String(e.seq)}`}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
