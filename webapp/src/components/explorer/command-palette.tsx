"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { KIND_LABEL, SOURCE_LABEL, type Source } from "@/lib/explorer/graph";
import { useEntitySearch } from "@/lib/explorer/queries";
import { cn } from "@/lib/utils";

import { entityHref, KIND_ICON } from "./common";

const SOURCES: Source[] = ["run", "course", "neo4j"];

/** Ctrl+K (or Cmd+K): jump to any user, device, card or IP by id prefix. */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [source, setSource] = useState<Source>("run");
  const [active, setActive] = useState(0);
  const listId = useId();
  const hits = useEntitySearch(open ? q : "", source, [], 10);
  const items = hits.data ?? [];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  function go(i: number) {
    const h = items[i];
    if (!h) return;
    setOpen(false);
    setQ("");
    router.push(entityHref(h.kind, h.id, source));
  }

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="text-muted-foreground hidden gap-2 sm:inline-flex"
        onClick={() => setOpen(true)}
      >
        <Search aria-hidden /> Search entities
        <kbd className="text-foreground rounded border px-1.5 font-mono text-[10px]">Ctrl K</kbd>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="sm:hidden"
        aria-label="Search entities"
        onClick={() => setOpen(true)}
      >
        <Search aria-hidden />
      </Button>
      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) setQ("");
        }}
      >
        <DialogContent className="gap-3 p-4 sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Search entities</DialogTitle>
            <DialogDescription>
              Users, devices, cards and IPs by id prefix. Arrow keys move, Enter opens.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap gap-1" role="group" aria-label="Graph to search">
            {SOURCES.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={s === source ? "default" : "outline"}
                aria-pressed={s === source}
                onClick={() => setSource(s)}
              >
                {SOURCE_LABEL[s]}
              </Button>
            ))}
          </div>
          <Input
            role="combobox"
            aria-label="Entity id"
            aria-expanded={items.length > 0}
            aria-controls={listId}
            aria-activedescendant={items[active] ? `${listId}-${active}` : undefined}
            aria-autocomplete="list"
            placeholder="u01, device_007, ip_001…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(items.length - 1, a + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(0, a - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                go(active);
              }
            }}
          />
          <ul id={listId} role="listbox" aria-label="Matches" className="max-h-72 overflow-y-auto">
            {items.map((h, i) => {
              const Icon = KIND_ICON[h.kind];
              return (
                <li
                  key={`${h.kind}:${h.id}`}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(i)}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                    i === active && "bg-accent text-accent-foreground",
                  )}
                >
                  <Icon className="size-4" aria-hidden />
                  <span className="font-mono">{h.id}</span>
                  <span className={cn("ml-auto text-xs", i !== active && "text-muted-foreground")}>
                    {KIND_LABEL[h.kind]} · {h.degree}
                  </span>
                </li>
              );
            })}
          </ul>
          {q.trim() && hits.error ? (
            <p className="text-destructive text-sm">{hits.error.message}</p>
          ) : q.trim() && hits.data && !items.length ? (
            <p className="text-muted-foreground text-sm">No matches.</p>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
