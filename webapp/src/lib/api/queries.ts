import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "./schema";
import { api, type HealthV1, toApiError, type UserOut } from "./client";

export type CreateUserRequest = components["schemas"]["CreateUserRequest"];
export type UpdateUserRequest = components["schemas"]["UpdateUserRequest"];

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

export function useUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: async (): Promise<UserOut[]> => {
      const { data, error, response } = await api.GET("/api/v1/admin/users", {
        params: { query: { limit: 200 } },
      });
      if (!data) throw toApiError(error, response);
      return data.items;
    },
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateUserRequest): Promise<UserOut> => {
      const { data, error, response } = await api.POST("/api/v1/admin/users", { body });
      if (!data) throw toApiError(error, response);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: UpdateUserRequest & { id: number }): Promise<UserOut> => {
      const { data, error, response } = await api.PATCH("/api/v1/admin/users/{user_id}", {
        params: { path: { user_id: id } },
        body,
      });
      if (!data) throw toApiError(error, response);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}
