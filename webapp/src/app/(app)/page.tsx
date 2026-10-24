import type { Metadata } from "next";

import { LiveDashboard } from "@/components/live/live-dashboard";
import { SystemStatusCard } from "@/components/system-status-card";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <LiveDashboard />
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <SystemStatusCard />
      </div>
    </div>
  );
}
