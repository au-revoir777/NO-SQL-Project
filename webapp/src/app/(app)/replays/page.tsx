import type { Metadata } from "next";

import { ReplayList } from "@/components/replay/replay-view";

export const metadata: Metadata = { title: "Replays" };

export default function ReplaysPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Replays</h1>
        <p className="text-muted-foreground text-sm">
          Story replays recorded by <code>fraudsim demo-story</code> and runs recorded by the API
          and the CLI.
        </p>
      </div>
      <ReplayList />
    </div>
  );
}
