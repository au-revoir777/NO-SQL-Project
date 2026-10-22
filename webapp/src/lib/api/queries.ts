import { useQuery } from "@tanstack/react-query";

import { api, type HealthV1, toApiError } from "./client";

export async function fetchHealth(): Promise<HealthV1> {
  const { data, error, response } = await api.GET("/api/v1/health");
  if (error !== undefined || data === undefined) {
    throw toApiError(error, response);
  }
  return data;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });
}
