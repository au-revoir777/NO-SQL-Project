import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AlertDetail } from "@/components/cases/alert-detail";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  return { title: `Alert ${(await params).id}` };
}

export default async function AlertPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id < 1) notFound();
  return <AlertDetail id={id} />;
}
