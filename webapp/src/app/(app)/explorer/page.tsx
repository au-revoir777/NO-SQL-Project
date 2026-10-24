import type { Metadata } from "next";
import { Suspense } from "react";

import { EntitySearch } from "@/components/explorer/entity-search";

export const metadata: Metadata = { title: "Explorer" };

export default function ExplorerPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Explorer</h1>
        <p className="text-muted-foreground">
          Investigate any user, device, card or IP: its links, transfers, alerts, and the
          neighbourhood the detector sees around it.
        </p>
      </div>
      <Suspense>
        <EntitySearch />
      </Suspense>
    </div>
  );
}
