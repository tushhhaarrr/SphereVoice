"use client";

/**
 * Calendly integration hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";
import type {
    CalendlyIntegrationListResponse,
    CalendlyInitiateResponse,
    CalendlySyncResponse,
} from "../types";

// ── Query keys ──────────────────────────────────────────────

export const calendlyKeys = {
    all: ["calendly-integrations"] as const,
    list: (tenantId?: string) => [...calendlyKeys.all, "list", tenantId] as const,
};

// ── Queries ──────────────────────────────────────────────────

export function useCalendlyIntegrations(tenantId?: string) {
    return useQuery<CalendlyIntegrationListResponse>({
        queryKey: calendlyKeys.list(tenantId),
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const qs = params.toString();
            try {
                const res = await fetchWithAuth(`/api/v1/integrations/calendly${qs ? `?${qs}` : ""}`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return { integrations: [], total: 0 } as CalendlyIntegrationListResponse;
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { integrations: [], total: 0 } as CalendlyIntegrationListResponse;
            }
        },
    });
}

// ── Mutations ────────────────────────────────────────────────

export function useInitiateCalendlyOAuth() {
    return useMutation<CalendlyInitiateResponse, Error, { tenantId?: string }>({
        mutationFn: async ({ tenantId }) => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/calendly/initiate?${params.toString()}`,
                { method: "POST" },
            );
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail ?? "Failed to initiate Calendly OAuth");
            }
            return res.json();
        },
        onSuccess: ({ auth_url }) => {
            window.location.href = auth_url;
        },
    });
}

export function useSyncCalendly(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<CalendlySyncResponse, Error, { integrationId: string }>({
        mutationFn: async ({ integrationId }) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/calendly/${integrationId}/sync${qs}`,
                { method: "POST" },
            );
            if (!res.ok) throw new Error("Failed to sync Calendly integration");
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: calendlyKeys.list(tenantId) });
        },
    });
}

export function useDisconnectCalendly(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<void, Error, { integrationId: string }>({
        mutationFn: async ({ integrationId }) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/calendly/${integrationId}${qs}`,
                { method: "DELETE" },
            );
            if (!res.ok) throw new Error("Failed to disconnect Calendly");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: calendlyKeys.list(tenantId) });
        },
    });
}

