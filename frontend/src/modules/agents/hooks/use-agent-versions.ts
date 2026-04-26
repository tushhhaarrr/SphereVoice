"use client";

/**
 * Agent version hooks — fetch version history and rollback.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AgentVersion } from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── Queries ─────────────────────────────────────────────────

interface AgentVersionsResponse {
  versions: AgentVersion[];
}

export function useAgentVersions(agentId: string) {
  return useQuery<AgentVersionsResponse>({
    queryKey: ["agent-versions", agentId],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/agents/${agentId}/versions`);
      if (!res.ok) throw new Error("Failed to fetch agent versions");
      return res.json();
    },
    enabled: !!agentId,
  });
}

// ── Mutations ───────────────────────────────────────────────

export function useRollbackAgent() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { agentId: string; version: number }>({
    mutationFn: async ({ agentId, version }) => {
      const res = await fetchWithAuth(
        `/api/v1/agents/${agentId}/rollback`,
        {
          method: "POST",
          body: JSON.stringify({ version }),
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error?.message || "Failed to rollback agent");
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      queryClient.invalidateQueries({ queryKey: ["agents", variables.agentId] });
      queryClient.invalidateQueries({ queryKey: ["agent-versions", variables.agentId] });
    },
  });
}
