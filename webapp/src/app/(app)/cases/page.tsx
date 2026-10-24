import type { Metadata } from "next";

import { CaseList } from "@/components/cases/case-list";

export const metadata: Metadata = { title: "Cases" };

export default function CasesPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Cases</h1>
        <p className="text-muted-foreground">
          Investigations that group alerts. Every change is written to the audit trail.
        </p>
      </div>
      <CaseList />
    </div>
  );
}
