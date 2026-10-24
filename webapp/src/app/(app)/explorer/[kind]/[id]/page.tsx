import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { EntityView } from "@/components/explorer/entity-view";
import { type EntityKind, KINDS } from "@/lib/explorer/graph";

type Params = Promise<{ kind: string; id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  return { title: decodeURIComponent((await params).id) };
}

export default async function EntityPage({ params }: { params: Params }) {
  const { kind, id } = await params;
  if (!KINDS.includes(kind as EntityKind)) notFound();
  return (
    <Suspense>
      <EntityView kind={kind as EntityKind} id={decodeURIComponent(id)} />
    </Suspense>
  );
}
