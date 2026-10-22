import type { Metadata } from "next";

import { PlannedPage } from "@/components/planned-page";

export const metadata: Metadata = { title: "Replays" };

export default function Page() {
  return <PlannedPage href="/replays" />;
}
