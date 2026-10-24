import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";

import { api, toApiError } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

import type { EntityKind, Neighbourhood, Rel, Source } from "./graph";

type S = components["schemas"];
export type EntityHit = S["EntityHit"];
export type EntityDetail = S["EntityDetail"];
export type RingView = S["RingViewOut"];

function ok<T>(r: { data?: T; error?: unknown; response: Response }): T {
  if (r.data === undefined) throw toApiError(r.error, r.response);
  return r.data;
}

export function useEntitySearch(q: string, source: Source, kinds: EntityKind[], limit = 20) {
  const query = q.trim();
  return useQuery({
    queryKey: ["entities", "search", source, query, kinds, limit],
    enabled: query.length > 0,
    queryFn: async () =>
      ok(
        await api.GET("/api/v1/entities/search", {
          params: { query: { q: query, source, limit, ...(kinds.length ? { kind: kinds } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
    staleTime: 5_000,
  });
}

export function useEntity(kind: EntityKind, id: string, source: Source) {
  return useQuery({
    queryKey: ["entities", source, kind, id],
    queryFn: async () =>
      ok(
        await api.GET("/api/v1/entities/{kind}/{entity_id}", {
          params: { path: { kind, entity_id: id }, query: { source } },
        }),
      ),
  });
}

export interface NeighbourhoodParams {
  k: number;
  rels: Rel[];
  since_t: number | null;
  until_t: number | null;
  max_fanout: number | null;
  far_fanout: number | null;
  max_nodes: number;
}

export const DEFAULT_PARAMS: NeighbourhoodParams = {
  k: 1,
  rels: ["device", "card", "ip", "transfer"],
  since_t: null,
  until_t: null,
  max_fanout: null,
  far_fanout: null,
  max_nodes: 400,
};

async function fetchNeighbourhood(
  seed: string,
  source: Source,
  p: NeighbourhoodParams,
): Promise<Neighbourhood> {
  return ok(
    await api.GET("/api/v1/graph/neighbourhood", {
      params: {
        query: {
          seed: [seed],
          source,
          k: p.k,
          rel: p.rels,
          max_nodes: p.max_nodes,
          ...(p.since_t !== null ? { since_t: p.since_t } : {}),
          ...(p.until_t !== null ? { until_t: p.until_t } : {}),
          ...(p.max_fanout !== null ? { max_fanout: p.max_fanout } : {}),
          ...(p.far_fanout !== null ? { far_fanout: p.far_fanout } : {}),
        },
      },
    }),
  );
}

/**
 * One neighbourhood per request: the main seeds (the entity, and a pinned one
 * to compare) with the chosen k, and every clicked node expanded by one hop.
 */
export function useNeighbourhoods(
  source: Source,
  seeds: string[],
  expanded: string[],
  p: NeighbourhoodParams,
) {
  return useQueries({
    queries: [
      ...seeds.map((seed) => ({
        queryKey: ["graph", source, seed, p],
        queryFn: () => fetchNeighbourhood(seed, source, p),
      })),
      ...expanded.map((seed) => ({
        queryKey: ["graph", source, seed, { ...p, k: 1 }],
        queryFn: () => fetchNeighbourhood(seed, source, { ...p, k: 1 }),
      })),
    ],
  });
}

export function useRing(ringId: string) {
  return useQuery({
    queryKey: ["graph", "ring", ringId],
    queryFn: async () =>
      ok(await api.GET("/api/v1/graph/rings/{ring_id}", { params: { path: { ring_id: ringId } } })),
  });
}
