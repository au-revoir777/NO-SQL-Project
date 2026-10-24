import type { Metadata } from "next";

import { ReplayView } from "@/components/replay/replay-view";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ runId: string }>;
}): Promise<Metadata> {
  return { title: `Replay ${(await params).runId}` };
}

export default async function ReplayPage({ params }: { params: Promise<{ runId: string }> }) {
  return <ReplayView runId={(await params).runId} />;
}
