import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";

/** Render with the app's client-side providers (no retries, so errors show at once). */
export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>{ui}</TooltipProvider>
    </QueryClientProvider>,
  );
}

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}
