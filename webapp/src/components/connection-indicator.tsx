"use client";

import { CircleCheck, CircleDashed, CircleX, TriangleAlert } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

/** API reachability from /api/v1/health. Colour is always paired with an icon and text. */
export function ConnectionIndicator() {
  const { data, isPending, isError } = useHealth();

  let label = "Checking API";
  let Icon = CircleDashed;
  let tone = "text-muted-foreground";
  if (isError) {
    label = "API unreachable";
    Icon = CircleX;
    tone = "text-risk-alert";
  } else if (!isPending && data) {
    if (data.status === "ok") {
      label = "API connected";
      Icon = CircleCheck;
      tone = "text-ok";
    } else {
      label = "API degraded";
      Icon = TriangleAlert;
      tone = "text-warn";
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span role="status" className={cn("flex items-center gap-1.5 text-xs font-medium", tone)}>
          <Icon className="size-4" aria-hidden />
          <span className="hidden sm:inline">{label}</span>
          <span className="sr-only sm:hidden">{label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{data ? `API ${data.version} (${data.api_version})` : label}</TooltipContent>
    </Tooltip>
  );
}
