import type { Metadata } from "next";

import { SystemStatusCard } from "@/components/system-status-card";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Live KPIs and the alert feed arrive in milestone P3. For now this page shows the state of
          the backend.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <SystemStatusCard />
      </div>
    </div>
  );
}
