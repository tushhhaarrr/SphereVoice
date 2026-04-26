"use client";

/**
 * CRM Data hooks — contacts, leads, deals from Zoho CRM via tenant-scoped integration.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";
import type {
    CachedContactListResponse,
    CrmCallFromCrmRequest,
    CrmCallFromCrmResponse,
    CrmSettingsResponse,
    CrmSettingsUpdateRequest,
    SyncStatusResponse,
    SyncTriggerResponse,
    ZohoCallerEnrichmentResponse,
    ZohoRecordListResponse,
} from "../types";

// ── Query keys ──────────────────────────────────────────────

export const crmDataKeys = {
    all: ["crm-data"] as const,
    contacts: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "contacts", params] as const,
    contact: (id: string) => [...crmDataKeys.all, "contact", id] as const,
    leads: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "leads", params] as const,
    deals: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "deals", params] as const,
    accounts: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "accounts", params] as const,
    tasks: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "tasks", params] as const,
    calls: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "calls", params] as const,
    notes: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "notes", params] as const,
    meetings: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "meetings", params] as const,
    campaigns: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "campaigns", params] as const,
    lookup: (phone: string) => [...crmDataKeys.all, "lookup", phone] as const,
    cachedContacts: (params?: Record<string, unknown>) =>
        [...crmDataKeys.all, "cached-contacts", params] as const,
    syncStatus: () => [...crmDataKeys.all, "sync-status"] as const,
};

// ── Contacts ────────────────────────────────────────────────

export function useCrmContacts({
    page = 1,
    perPage = 50,
    search,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    search?: string;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, search, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.contacts(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (search) qs.set("search", search);
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/contacts?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM contacts");
            return res.json();
        },
        enabled,
    });
}

export function useCrmContact(contactId: string, tenantId?: string, enabled = true) {
    return useQuery({
        queryKey: crmDataKeys.contact(contactId),
        queryFn: async () => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/contacts/${contactId}${qs}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM contact");
            return res.json();
        },
        enabled: enabled && !!contactId,
    });
}

// ── Leads ───────────────────────────────────────────────────

export function useCrmLeads({
    page = 1,
    perPage = 50,
    search,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    search?: string;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, search, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.leads(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (search) qs.set("search", search);
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/leads?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM leads");
            return res.json();
        },
        enabled,
    });
}

// ── Deals ───────────────────────────────────────────────────

export function useCrmDeals({
    page = 1,
    perPage = 50,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.deals(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/deals?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM deals");
            return res.json();
        },
        enabled,
    });
}

// ── Accounts ────────────────────────────────────────────────

export function useCrmAccounts({
    page = 1,
    perPage = 50,
    search,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    search?: string;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, search, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.accounts(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (search) qs.set("search", search);
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/accounts?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM accounts");
            return res.json();
        },
        enabled,
    });
}

// ── Tasks ───────────────────────────────────────────────────

export function useCrmTasks({
    page = 1,
    perPage = 50,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.tasks(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/tasks?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM tasks");
            return res.json();
        },
        enabled,
    });
}

// ── Calls ───────────────────────────────────────────────────

export function useCrmCalls({
    page = 1,
    perPage = 50,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.calls(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/calls?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM calls");
            return res.json();
        },
        enabled,
    });
}

// ── Notes ───────────────────────────────────────────────────

export function useCrmNotes({
    page = 1,
    perPage = 50,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.notes(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/notes?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM notes");
            return res.json();
        },
        enabled,
    });
}

// ── Meetings ────────────────────────────────────────────────

export function useCrmMeetings({
    page = 1,
    perPage = 50,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.meetings(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/meetings?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM meetings");
            return res.json();
        },
        enabled,
    });
}

// ── Campaigns ───────────────────────────────────────────────

export function useCrmCampaigns({
    page = 1,
    perPage = 50,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, tenantId };
    return useQuery<ZohoRecordListResponse>({
        queryKey: crmDataKeys.campaigns(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/campaigns?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch CRM campaigns");
            return res.json();
        },
        enabled,
    });
}

// ── Caller lookup ───────────────────────────────────────────

export function useCrmCallerLookup(phone: string, tenantId?: string, enabled = true) {
    return useQuery<ZohoCallerEnrichmentResponse>({
        queryKey: crmDataKeys.lookup(phone),
        queryFn: async () => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/lookup/${encodeURIComponent(phone)}${qs}`
            );
            if (!res.ok) throw new Error("Failed to look up caller");
            return res.json();
        },
        enabled: enabled && !!phone,
    });
}

// ── Click-to-call ───────────────────────────────────────────

export function useCallFromCrm(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<CrmCallFromCrmResponse, Error, CrmCallFromCrmRequest>({
        mutationFn: async (body) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(`/api/v1/integrations/crm/call-from-crm${qs}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.message || "Failed to initiate call");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["calls"] });
        },
    });
}

// ── CRM Settings ────────────────────────────────────────────

export const crmSettingsKeys = {
    all: ["crm-settings"] as const,
};

export function useCrmSettings(tenantId?: string) {
    return useQuery<CrmSettingsResponse>({
        queryKey: [...crmSettingsKeys.all, tenantId],
        queryFn: async () => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(`/api/v1/integrations/crm/settings${qs}`);
            if (!res.ok) throw new Error("Failed to load CRM settings");
            return res.json();
        },
    });
}

export function useUpdateCrmSettings(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<CrmSettingsResponse, Error, CrmSettingsUpdateRequest>({
        mutationFn: async (body) => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(`/api/v1/integrations/crm/settings${qs}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(
                    err?.detail?.error?.message || "Failed to update CRM settings"
                );
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: crmSettingsKeys.all });
        },
    });
}

// ── Cached Contacts ─────────────────────────────────────────

export function useCachedContacts({
    page = 1,
    perPage = 50,
    search,
    module,
    tenantId,
    enabled = true,
}: {
    page?: number;
    perPage?: number;
    search?: string;
    module?: string;
    tenantId?: string;
    enabled?: boolean;
} = {}) {
    const params = { page, perPage, search, module, tenantId };
    return useQuery<CachedContactListResponse>({
        queryKey: crmDataKeys.cachedContacts(params),
        queryFn: async () => {
            const qs = new URLSearchParams();
            qs.set("page", String(page));
            qs.set("per_page", String(perPage));
            if (search) qs.set("search", search);
            if (module) qs.set("module", module);
            if (tenantId) qs.set("tenant_id", tenantId);
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/cache/contacts?${qs.toString()}`
            );
            if (!res.ok) throw new Error("Failed to fetch cached contacts");
            return res.json();
        },
        enabled,
    });
}

// ── Sync Status ─────────────────────────────────────────────

export function useSyncStatus(tenantId?: string, enabled = true) {
    return useQuery<SyncStatusResponse>({
        queryKey: [...crmDataKeys.syncStatus(), tenantId],
        queryFn: async () => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/sync/status${qs}`
            );
            if (!res.ok) throw new Error("Failed to fetch sync status");
            return res.json();
        },
        enabled,
        refetchInterval: 30_000, // Poll every 30s for live progress
    });
}

export function useTriggerSync(tenantId?: string) {
    const queryClient = useQueryClient();
    return useMutation<SyncTriggerResponse, Error>({
        mutationFn: async () => {
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/integrations/crm/sync/trigger${qs}`,
                { method: "POST" }
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.message || "Failed to trigger sync");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: crmDataKeys.syncStatus() });
            // Refresh cached contacts after a short delay
            setTimeout(() => {
                queryClient.invalidateQueries({ queryKey: crmDataKeys.all });
            }, 5000);
        },
    });
}
