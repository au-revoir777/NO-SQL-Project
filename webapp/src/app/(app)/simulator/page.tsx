import type { Metadata } from "next";

import { Simulator } from "@/components/simulator/simulator";

export const metadata: Metadata = { title: "Simulator" };

export default function SimulatorPage() {
  return <Simulator />;
}
