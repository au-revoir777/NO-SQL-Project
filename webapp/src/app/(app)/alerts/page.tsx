import type { Metadata } from "next";

import { AlertQueue } from "@/components/cases/alert-queue";

export const metadata: Metadata = { title: "Alerts" };

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <p className="text-muted-foreground">
          Alerts and early warnings recorded from live runs. Triage them, label them, and group them
          into cases.
        </p>
      </div>
      <AlertQueue />
    </div>
  );
}
