"use client";

/**
 * Google Calendar & Sheets integration hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";
import type {
    GoogleIntegrationListResponse,
    GoogleInitiateResponse,
    GoogleSyncResponse,
} from "../types";

// ── Query keys ──────────────────────────────────────────────

export const googleKeys = {
    all: ["google-integrations"] as const,
    calendar: (tenantId?: string) => [...googleKeys.all, "calendar", tenantId] as const,
    sheets: (tenantId?: string) => [...googleKeys.all, "sheets", tenantId] as const,
};

// ── Calendar queries ────────────────────────────────────────

export function useGoogleCalendarIntegrations(tenantId?: string) {
    return useQuery<GoogleIntegrationListResponse>({
        queryKey: googleKeys.calendar(tenantId),
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const qs = params.toString();
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/calendar${qs ? `?${qs}` : ""}`,
            );
            if (!res.ok) throw new Error("Failed to fetch Google Calendar integrations");
            return res.json();
        },
    });
}

export function useInitiateGoogleCalendarOAuth() {
    return useMutation<GoogleInitiateResponse, Error, { tenantId?: string }>({
        mutationFn: async ({ tenantId }) => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/calendar/initiate?${params.toString()}`,
                { method: "POST" },
            );
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail ?? "Failed to initiate Google Calendar OAuth");
            }
            return res.json();
        },
        onSuccess: ({ auth_url }) => {
            window.location.href = auth_url;
        },
    });
}

export function useSyncGoogleCalendar(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<GoogleSyncResponse, Error, { integrationId: string }>({
        mutationFn: async ({ integrationId }) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/calendar/${integrationId}/sync${qs}`,
                { method: "POST" },
            );
            if (!res.ok) throw new Error("Failed to sync Google Calendar integration");
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: googleKeys.calendar(tenantId) });
        },
    });
}

export function useDisconnectGoogleCalendar(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<void, Error, { integrationId: string }>({
        mutationFn: async ({ integrationId }) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/calendar/${integrationId}${qs}`,
                { method: "DELETE" },
            );
            if (!res.ok) throw new Error("Failed to disconnect Google Calendar");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: googleKeys.calendar(tenantId) });
        },
    });
}

// ── Sheets queries ──────────────────────────────────────────

export function useGoogleSheetsIntegrations(tenantId?: string) {
    return useQuery<GoogleIntegrationListResponse>({
        queryKey: googleKeys.sheets(tenantId),
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const qs = params.toString();
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets${qs ? `?${qs}` : ""}`,
            );
            if (!res.ok) throw new Error("Failed to fetch Google Sheets integrations");
            return res.json();
        },
    });
}

export function useInitiateGoogleSheetsOAuth() {
    return useMutation<GoogleInitiateResponse, Error, { tenantId?: string }>({
        mutationFn: async ({ tenantId }) => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets/initiate?${params.toString()}`,
                { method: "POST" },
            );
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail ?? "Failed to initiate Google Sheets OAuth");
            }
            return res.json();
        },
        onSuccess: ({ auth_url }) => {
            window.location.href = auth_url;
        },
    });
}

export function useSyncGoogleSheets(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<GoogleSyncResponse, Error, { integrationId: string }>({
        mutationFn: async ({ integrationId }) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets/${integrationId}/sync${qs}`,
                { method: "POST" },
            );
            if (!res.ok) throw new Error("Failed to sync Google Sheets integration");
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: googleKeys.sheets(tenantId) });
        },
    });
}

export function useDisconnectGoogleSheets(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<void, Error, { integrationId: string }>({
        mutationFn: async ({ integrationId }) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets/${integrationId}${qs}`,
                { method: "DELETE" },
            );
            if (!res.ok) throw new Error("Failed to disconnect Google Sheets");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: googleKeys.sheets(tenantId) });
        },
    });
}
