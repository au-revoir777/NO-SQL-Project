import type { Metadata } from "next";
import { Suspense } from "react";

import { ReportBuilder } from "@/components/reports/report-builder";
import { ReportsList } from "@/components/reports/reports-list";

export const metadata: Metadata = { title: "Reports" };

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
        <p className="text-muted-foreground">
          Investigation reports as HTML or PDF, with the evidence, the analysts&apos; notes, run
          metrics and a SAR-style summary. Generated from simulated data for research and demo
          purposes; not a regulatory filing.
        </p>
      </div>
      <Suspense>
        <ReportBuilder />
      </Suspense>
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Generated reports</h2>
        <ReportsList />
      </section>
    </div>
  );
}
