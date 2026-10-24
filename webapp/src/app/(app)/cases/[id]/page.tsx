import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CaseDetail } from "@/components/cases/case-detail";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  return { title: `Case ${(await params).id}` };
}

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id < 1) notFound();
  return <CaseDetail id={id} />;
}
