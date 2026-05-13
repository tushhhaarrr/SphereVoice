"use client";

/**
 * Agent data-fetching hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Agent, AgentCreateRequest, AgentListResponse } from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── Queries ─────────────────────────────────────────────────

export function useAgents(params?: { page?: number; limit?: number; status?: string; type?: string; tenantId?: string }) {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.status) search.set("status", params.status);
    if (params?.type) search.set("type", params.type);
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<AgentListResponse>({
        queryKey: ["agents", params],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/agents${qs}`);
                if (res.status === 401 || res.status === 403) {
                    throw new Error("Unauthorized");
                }
                if (!res.ok) {
                    return { agents: [], total: 0, page: 1, limit: 50 } as AgentListResponse;
                }
                const json = await res.json();
                // Normalize: backend uses `nodes` + `total_count`, components use `agents` + `total`
                if (json.nodes !== undefined && json.agents === undefined) {
                    json.agents = json.nodes;
                    json.total = json.total_count ?? json.nodes.length;
                    json.page = json.cursor_position ?? 1;
                    json.limit = json.limit_bound ?? 50;
                }
                return json as AgentListResponse;
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { agents: [], total: 0, page: 1, limit: 50 } as AgentListResponse;
            }
        },
    });
}

export function useAgent(id: string) {
    return useQuery<Agent>({
        queryKey: ["agents", id],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/agents/${id}`);
            if (!res.ok) throw new Error("Failed to fetch agent");
            return res.json();
        },
        enabled: !!id,
    });
}

// ── Mutations ───────────────────────────────────────────────

export function useCreateAgent() {
    const queryClient = useQueryClient();

    return useMutation<Agent, Error, AgentCreateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/agents", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to create agent");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
        },
    });
}

export function useDeleteAgent() {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/agents/${id}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error("Failed to delete agent");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
        },
    });
}

export function useUpdateAgent() {
    const queryClient = useQueryClient();

    return useMutation<Agent, Error, { id: string; data: Partial<Agent> }>({
        mutationFn: async ({ id, data }) => {
            const res = await fetchWithAuth(`/api/v1/agents/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to update agent");
            }
            return res.json();
        },
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
            queryClient.invalidateQueries({ queryKey: ["agents", variables.id] });
        },
    });
}

export function usePublishAgent() {
    const queryClient = useQueryClient();

    return useMutation<Agent, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/agents/${id}/publish`, {
                method: "POST",
            });
            if (!res.ok) throw new Error("Failed to publish agent");
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
        },
    });
}

// ── AI Generation ───────────────────────────────────────────

export interface AIGenerateResult {
    name: string;
    system_prompt: string;
    welcome_message: string;
    variables?: Array<{ name: string; description: string; default_value: string; category: string }>;
}

export interface AIGenerateRequest {
    description: string;
    kb_context?: string;
    language?: string;
    voice_gender?: string | null;
    call_direction?: "inbound" | "outbound";
    crm_fields?: string[];
}

export function useAIGenerateAgent() {
    return useMutation<AIGenerateResult, Error, AIGenerateRequest>({
        mutationFn: async ({ description, kb_context, language, voice_gender, call_direction, crm_fields }) => {
            const res = await fetchWithAuth("/api/v1/agents/ai/generate", {
                method: "POST",
                body: JSON.stringify({ description, kb_context, language, voice_gender, call_direction, crm_fields }),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "AI generation failed" }));
                throw new Error(err.detail || "AI generation failed");
            }
            return res.json();
        },
    });
}

// ── 2-Step AI Generation ────────────────────────────────────

export interface AIGenerateBaseRequest {
    description: string;
    kb_context?: string;
    language?: string;
    voice_gender?: string | null;
    call_direction?: "inbound" | "outbound";
    crm_fields?: string[];
}

export interface AIGenerateBaseResult {
    name: string;
    system_prompt: string;
    welcome_message: string;
    recommended_crm_fields: string[];
}

export function useAIGenerateBase() {
    return useMutation<AIGenerateBaseResult, Error, AIGenerateBaseRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/agents/ai/generate-base", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "AI generation failed" }));
                throw new Error(err.detail || "AI generation failed");
            }
            return res.json();
        },
    });
}

export interface AIFinalizeRequest {
    system_prompt: string;
    welcome_message: string;
    selected_crm_fields: string[];
    call_direction?: "inbound" | "outbound";
}

export interface AIFinalizeResult {
    system_prompt: string;
    welcome_message: string;
    variables: Array<{ name: string; description: string; default_value: string; category: string }>;
}

export function useAIFinalize() {
    return useMutation<AIFinalizeResult, Error, AIFinalizeRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/agents/ai/finalize", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "AI finalization failed" }));
                throw new Error(err.detail || "AI finalization failed");
            }
            return res.json();
        },
    });
}

// ── AI Translation ──────────────────────────────────────────

export interface TranslateTextRequest {
    text: string;
    target_language: string;
    text_type: "system_prompt" | "welcome_message";
    voice_gender?: string | null;
}

export interface TranslateTextResult {
    translated_text: string;
    target_language: string;
}

export function useTranslateAgentText() {
    return useMutation<TranslateTextResult, Error, TranslateTextRequest>({
        mutationFn: async ({ text, target_language, text_type, voice_gender }) => {
            const res = await fetchWithAuth("/api/v1/agents/ai/translate", {
                method: "POST",
                body: JSON.stringify({ text, target_language, text_type, voice_gender }),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Translation failed" }));
                throw new Error(err.detail || "Translation failed");
            }
            return res.json();
        },
    });
}
