"use client";

/**
 * Template data-fetching hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
    AgentTemplate,
    TemplateCreateAgentRequest,
    TemplateCreateRequest,
    TemplateListResponse,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── Queries ─────────────────────────────────────────────────

export function useTemplates(params?: {
    category?: string;
    builtinOnly?: boolean;
}) {
    const search = new URLSearchParams();
    if (params?.category) search.set("category", params.category);
    if (params?.builtinOnly) search.set("builtin_only", "true");
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<TemplateListResponse>({
        queryKey: ["templates", params],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/analytics/templates${qs}`);
            if (!res.ok) throw new Error("Failed to fetch templates");
            return res.json();
        },
    });
}

export function useTemplate(id: string) {
    return useQuery<AgentTemplate>({
        queryKey: ["templates", id],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/analytics/templates/${id}`);
            if (!res.ok) throw new Error("Failed to fetch template");
            return res.json();
        },
        enabled: !!id,
    });
}

// ── Mutations ───────────────────────────────────────────────

export function useCreateTemplate() {
    const queryClient = useQueryClient();

    return useMutation<AgentTemplate, Error, TemplateCreateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/analytics/templates", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to create template");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["templates"] });
        },
    });
}

export function useTemplateToAgent() {
    const queryClient = useQueryClient();

    return useMutation<
        { id: string; name: string; type: string; status: string; template_id: string },
        Error,
        { templateId: string; data: TemplateCreateAgentRequest }
    >({
        mutationFn: async ({ templateId, data }) => {
            const res = await fetchWithAuth(
                `/api/v1/analytics/templates/${templateId}/use`,
                {
                    method: "POST",
                    body: JSON.stringify(data),
                }
            );
            if (!res.ok) {
                const err = await res.json();
                throw new Error(
                    err.error?.message || "Failed to create agent from template"
                );
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
            queryClient.invalidateQueries({ queryKey: ["templates"] });
        },
    });
}
