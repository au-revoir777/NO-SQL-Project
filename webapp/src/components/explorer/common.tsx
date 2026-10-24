"use client";

import { CreditCard, Globe, Smartphone, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type EntityKind, SOURCE_LABEL, type Source } from "@/lib/explorer/graph";
import { cn } from "@/lib/utils";

export const KIND_ICON = { user: UserRound, device: Smartphone, card: CreditCard, ip: Globe };

const SOURCES: Source[] = ["run", "course", "neo4j"];

/** The graph being explored, kept in the URL (?source=), default: the current run. */
export function useSource(): Source {
  const s = useSearchParams().get("source");
  return SOURCES.includes(s as Source) ? (s as Source) : "run";
}

export function entityHref(kind: EntityKind, id: string, source: Source): string {
  const q = source === "run" ? "" : `?source=${source}`;
  return `/explorer/${kind}/${encodeURIComponent(id)}${q}`;
}

export function EntityLink({
  kind,
  id,
  source,
  className,
}: {
  kind: EntityKind;
  id: string;
  source: Source;
  className?: string;
}) {
  const Icon = KIND_ICON[kind];
  return (
    <Link
      href={entityHref(kind, id, source)}
      className={cn(
        "inline-flex items-center gap-1 font-mono text-xs underline-offset-4 hover:underline",
        className,
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden />
      {id}
    </Link>
  );
}

export function SourceSelect() {
  const source = useSource();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  return (
    <div className="space-y-1">
      <Label htmlFor="explorer-source">Graph</Label>
      <Select
        value={source}
        onValueChange={(v) => {
          const next = new URLSearchParams(params.toString());
          if (v === "run") next.delete("source");
          else next.set("source", v);
          const q = next.toString();
          router.replace(q ? `${pathname}?${q}` : pathname);
        }}
      >
        <SelectTrigger id="explorer-source" className="w-52">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {SOURCES.map((s) => (
            <SelectItem key={s} value={s}>
              {SOURCE_LABEL[s]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
