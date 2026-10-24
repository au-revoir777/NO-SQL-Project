import type { Metadata } from "next";

import { RingView } from "@/components/explorer/ring-view";

type Params = Promise<{ ringId: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  return { title: `Ring ${(await params).ringId}` };
}

export default async function RingPage({ params }: { params: Params }) {
  return <RingView ringId={(await params).ringId} />;
}
