"use client";

/**
 * TanStack Query hooks for the Tool Registry API (/api/v1/tools).
 *
 * Covers:
 * - Listing tenant tools (available tools for the workspace)
 * - Listing tools bound to a specific agent
 * - Binding / unbinding tools from an agent
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";

// ── Types ────────────────────────────────────────────────────

export interface TenantTool {
    id: string;
    tenant_id: string;
    integration_id: string | null;
    name: string;
    display_name: string;
    description: string;
    category: string;
    parameters_schema: Record<string, unknown>;
    execution_type: string;
    execution_config: Record<string, unknown>;
    is_active: boolean;
}

export interface AgentToolBinding {
    agent_id: string;
    tool_id: string;
    config: Record<string, unknown>;
    tool: TenantTool;
}

interface TenantToolListResponse {
    items: TenantTool[];
    total: number;
    skip: number;
    limit: number;
}

// ── Query keys ───────────────────────────────────────────────

export const toolKeys = {
    all: ["tools"] as const,
    tenant: (tenantId?: string) => [...toolKeys.all, "tenant", tenantId] as const,
    agentTools: (agentId: string) => [...toolKeys.all, "agent", agentId] as const,
};

// ── Tenant Tools (workspace-level) ──────────────────────────

export function useTenantTools(tenantId?: string) {
    return useQuery<TenantToolListResponse>({
        queryKey: toolKeys.tenant(tenantId),
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            params.set("limit", "200");
            const res = await fetchWithAuth(`/api/v1/tools?${params.toString()}`);
            if (!res.ok) throw new Error("Failed to fetch tools");
            return res.json();
        },
        enabled: !!tenantId,
    });
}

// ── Agent Tool Bindings ─────────────────────────────────────

export function useAgentTools(agentId: string, tenantId?: string) {
    return useQuery<AgentToolBinding[]>({
        queryKey: toolKeys.agentTools(agentId),
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/tools/agents/${agentId}?${params.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch agent tools");
            return res.json();
        },
        enabled: !!agentId,
    });
}

export function useBindTool(agentId: string, tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<AgentToolBinding, Error, { toolId: string; config?: Record<string, unknown> }>({
        mutationFn: async ({ toolId, config }) => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/tools/agents/${agentId}/bind?${params.toString()}`,
                {
                    method: "POST",
                    body: JSON.stringify({ tool_id: toolId, config: config ?? {} }),
                }
            );
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail ?? "Failed to bind tool");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: toolKeys.agentTools(agentId) });
        },
    });
}

export function useUnbindTool(agentId: string, tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<void, Error, { toolId: string }>({
        mutationFn: async ({ toolId }) => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/tools/agents/${agentId}/tools/${toolId}?${params.toString()}`,
                { method: "DELETE" }
            );
            if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new Error(body?.detail ?? "Failed to unbind tool");
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: toolKeys.agentTools(agentId) });
        },
    });
}

// ── Google integration data hooks ────────────────────────────

export interface CalendarEntry {
    id: string;
    summary: string | null;
    description: string | null;
    primary: boolean;
}

export interface SpreadsheetEntry {
    id: string;
    name: string;
    modified_time: string | null;
    web_view_link: string | null;
}

export interface SheetTab {
    sheet_id: number;
    title: string;
    index: number;
}

/**
 * Fetch calendars visible to the connected Google Calendar account.
 */
export function useGoogleCalendars(
    integrationId: string | null | undefined,
    tenantId?: string
) {
    return useQuery<CalendarEntry[]>({
        queryKey: ["google-calendars", integrationId],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/calendar/${integrationId}/calendars?${params.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch calendars");
            const data = await res.json();
            return data.calendars;
        },
        enabled: !!integrationId,
        staleTime: 5 * 60 * 1000, // cache 5 min
    });
}

/**
 * Fetch spreadsheets visible to the connected Google Sheets account.
 */
export function useGoogleSpreadsheets(
    integrationId: string | null | undefined,
    tenantId?: string
) {
    return useQuery<SpreadsheetEntry[]>({
        queryKey: ["google-spreadsheets", integrationId],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets/${integrationId}/spreadsheets?${params.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch spreadsheets");
            const data = await res.json();
            return data.spreadsheets;
        },
        enabled: !!integrationId,
        staleTime: 5 * 60 * 1000,
    });
}

/**
 * Fetch sheet tabs for a specific spreadsheet.
 */
export function useGoogleSheetTabs(
    integrationId: string | null | undefined,
    spreadsheetId: string | null | undefined,
    tenantId?: string
) {
    return useQuery<SheetTab[]>({
        queryKey: ["google-sheet-tabs", integrationId, spreadsheetId],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets/${integrationId}/spreadsheets/${spreadsheetId}?${params.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch sheet tabs");
            const data = await res.json();
            return data.sheets;
        },
        enabled: !!integrationId && !!spreadsheetId,
        staleTime: 5 * 60 * 1000,
    });
}

/**
 * Fetch header row (first row) from a specific sheet tab.
 * Uses the existing read-rows endpoint with range=SheetName!1:1.
 */
export function useGoogleSheetHeaders(
    integrationId: string | null | undefined,
    spreadsheetId: string | null | undefined,
    sheetName: string | null | undefined,
    tenantId?: string
) {
    return useQuery<string[]>({
        queryKey: ["google-sheet-headers", integrationId, spreadsheetId, sheetName],
        queryFn: async () => {
            const range = `${sheetName}!1:1`;
            const params = new URLSearchParams({ range });
            if (tenantId) params.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/google/sheets/${integrationId}/spreadsheets/${spreadsheetId}/rows?${params.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch sheet headers");
            const data = await res.json();
            // data.values is [[header1, header2, ...]]
            return data.values?.[0]?.filter((h: string) => h?.trim()) ?? [];
        },
        enabled: !!integrationId && !!spreadsheetId && !!sheetName,
        staleTime: 5 * 60 * 1000,
    });
}
