import type { Metadata } from "next";

import { PlannedPage } from "@/components/planned-page";

export const metadata: Metadata = { title: "Cases" };

export default function Page() {
  return <PlannedPage href="/cases" />;
}
