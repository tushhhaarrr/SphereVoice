"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";
import type {
    TestScenario,
    TestScenarioCreate,
    TestScenarioListResponse,
    TestScenarioUpdate,
    TestCallResultListResponse,
} from "../types";

export const scenarioKeys = {
    all: (agentId: string) => ["test-scenarios", agentId] as const,
    detail: (agentId: string, scenarioId: string) =>
        ["test-scenarios", agentId, scenarioId] as const,
    results: (agentId: string, scenarioId: string) =>
        ["test-scenario-results", agentId, scenarioId] as const,
};

export function useTestScenarios(agentId: string) {
    return useQuery<TestScenarioListResponse>({
        queryKey: scenarioKeys.all(agentId),
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/agents/${agentId}/test-scenarios`);
            if (!res.ok) throw new Error("Failed to fetch test scenarios");
            return res.json();
        },
        enabled: !!agentId,
    });
}

export function useTestScenario(agentId: string, scenarioId: string) {
    return useQuery<TestScenario>({
        queryKey: scenarioKeys.detail(agentId, scenarioId),
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/agents/${agentId}/test-scenarios/${scenarioId}`);
            if (!res.ok) throw new Error("Failed to fetch test scenario");
            return res.json();
        },
        enabled: !!agentId && !!scenarioId,
    });
}

export function useCreateScenario(agentId: string) {
    const qc = useQueryClient();
    return useMutation<TestScenario, Error, TestScenarioCreate>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth(`/api/v1/agents/${agentId}/test-scenarios`, {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) throw new Error("Failed to create test scenario");
            return res.json();
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: scenarioKeys.all(agentId) });
        },
    });
}

export function useUpdateScenario(agentId: string, scenarioId: string) {
    const qc = useQueryClient();
    return useMutation<TestScenario, Error, TestScenarioUpdate>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth(
                `/api/v1/agents/${agentId}/test-scenarios/${scenarioId}`,
                { method: "PUT", body: JSON.stringify(data) },
            );
            if (!res.ok) throw new Error("Failed to update test scenario");
            return res.json();
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: scenarioKeys.all(agentId) });
            qc.invalidateQueries({
                queryKey: scenarioKeys.detail(agentId, scenarioId),
            });
        },
    });
}

export function useDeleteScenario(agentId: string) {
    const qc = useQueryClient();
    return useMutation<void, Error, string>({
        mutationFn: async (scenarioId) => {
            const res = await fetchWithAuth(
                `/api/v1/agents/${agentId}/test-scenarios/${scenarioId}`,
                { method: "DELETE" },
            );
            if (!res.ok) throw new Error("Failed to delete test scenario");
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: scenarioKeys.all(agentId) });
        },
    });
}

export function useScenarioResults(agentId: string, scenarioId: string) {
    return useQuery<TestCallResultListResponse>({
        queryKey: scenarioKeys.results(agentId, scenarioId),
        queryFn: async () => {
            const res = await fetchWithAuth(
                `/api/v1/agents/${agentId}/test-scenarios/${scenarioId}/results`,
            );
            if (!res.ok) throw new Error("Failed to fetch scenario results");
            return res.json();
        },
        enabled: !!agentId && !!scenarioId,
    });
}

export function useRunScenario(agentId: string) {
    const qc = useQueryClient();

    interface RunScenarioResponse {
        call_id: string;
        token: string;
        room_name: string;
        livekit_url: string;
        scenario_id: string;
    }

    return useMutation<
        RunScenarioResponse,
        Error,
        { scenarioId: string; agentVersion?: number | null }
    >({
        mutationFn: async ({ scenarioId, agentVersion }) => {
            const res = await fetchWithAuth(
                `/api/v1/agents/${agentId}/test-scenarios/${scenarioId}/run`,
                {
                    method: "POST",
                    body: JSON.stringify({ agent_version: agentVersion ?? null }),
                },
            );
            if (!res.ok) throw new Error("Failed to run test scenario");
            return res.json();
        },
        onSuccess: (_data, { scenarioId }) => {
            qc.invalidateQueries({
                queryKey: scenarioKeys.results(agentId, scenarioId),
            });
        },
    });
}
