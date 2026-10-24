import type { Metadata } from "next";

import { AuditView } from "@/components/cases/audit-view";

export const metadata: Metadata = { title: "Audit" };

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Audit</h1>
        <p className="text-muted-foreground">
          The app audit trail: sign-ins, user changes, triage, labels, notes and cases. Each entry
          is hash-chained to the one before it.
        </p>
      </div>
      <AuditView />
    </div>
  );
}
