"use client";

/**
 * Provider data-fetching hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
    Provider,
    ProviderCreateRequest,
    ProviderListResponse,
    ProviderTestResponse,
    ProviderUpdateRequest,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── Queries ─────────────────────────────────────────────────

export interface ProviderListParams {
    category?: string;
    tenantId?: string;
    enabled?: boolean;
}

export function useProviders(category?: string) {
    return useProvidersList({ category });
}

export function useProvidersList(params?: ProviderListParams) {
    return useQuery<ProviderListResponse>({
        queryKey: ["providers", params],
        queryFn: async () => {
            const search = new URLSearchParams();
            if (params?.category) {
                search.set("category", params.category);
            }
            if (params?.tenantId) {
                search.set("tenant_id", params.tenantId);
            }
            const qs = search.toString() ? `?${search.toString()}` : "";
            const res = await fetchWithAuth(`/api/v1/providers${qs}`);
            if (!res.ok) throw new Error("Failed to fetch providers");
            return res.json();
        },
        enabled: params?.enabled ?? true,
    });
}

export function useProvider(id: string) {
    return useQuery<Provider>({
        queryKey: ["providers", id],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/providers/${id}`);
            if (!res.ok) throw new Error("Failed to fetch provider");
            return res.json();
        },
        enabled: !!id,
    });
}

// ── Mutations ───────────────────────────────────────────────

export function useCreateProvider() {
    const queryClient = useQueryClient();

    return useMutation<Provider, Error, ProviderCreateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/providers", {
                method: "POST",
                body: JSON.stringify({
                    provider_name: data.provider_name,
                    provider_category: data.category,
                    api_key: data.api_key,
                    is_default: data.is_default,
                    tenant_id: data.tenant_id,
                    config: data.config,
                }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to create provider");
            }
            const provider: Provider = await res.json();
            if (provider.provider_category !== "telephony") {
                const refreshRes = await fetchWithAuth(`/api/v1/providers/${provider.id}/refresh`, {
                    method: "POST",
                });
                if (refreshRes.ok) {
                    return refreshRes.json();
                }
            }
            return provider;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["providers"] });
        },
    });
}

export function useUpdateProvider(id: string) {
    const queryClient = useQueryClient();

    return useMutation<Provider, Error, ProviderUpdateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth(`/api/v1/providers/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to update provider");
            }
            const provider: Provider = await res.json();
            if (provider.provider_category !== "telephony") {
                const refreshRes = await fetchWithAuth(`/api/v1/providers/${provider.id}/refresh`, {
                    method: "POST",
                });
                if (refreshRes.ok) {
                    return refreshRes.json();
                }
            }
            return provider;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["providers"] });
        },
    });
}

export function useDeleteProvider() {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/providers/${id}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error("Failed to delete provider");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["providers"] });
        },
    });
}

export function useTestProvider() {
    return useMutation<ProviderTestResponse, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/providers/${id}/test`, {
                method: "POST",
            });
            if (!res.ok) throw new Error("Failed to test provider");
            return res.json();
        },
    });
}

export function useRefreshProvider() {
    const queryClient = useQueryClient();

    return useMutation<Provider, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/providers/${id}/refresh`, {
                method: "POST",
            });
            if (!res.ok) throw new Error("Failed to refresh provider catalog");
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["providers"] });
        },
    });
}
