import type { Metadata } from "next";

import { PlannedPage } from "@/components/planned-page";

export const metadata: Metadata = { title: "Reports" };

export default function Page() {
  return <PlannedPage href="/reports" />;
}
