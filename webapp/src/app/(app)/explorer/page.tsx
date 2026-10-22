import type { Metadata } from "next";

import { PlannedPage } from "@/components/planned-page";

export const metadata: Metadata = { title: "Explorer" };

export default function Page() {
  return <PlannedPage href="/explorer" />;
}
