"use client";

/**
 * CRM Integration hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";
import type {
  CrmIntegrationListResponse,
  TenantIntegration,
  TenantIntegrationCreate,
  TenantIntegrationListResponse,
  TenantIntegrationUpdate,
  ZohoDataCenter,
  ZohoInitiateResponse,
  ZohoSyncResponse,
} from "../types";

// ── Query keys ──────────────────────────────────────────────

export const integrationKeys = {
  all: ["integrations"] as const,
  crm: () => [...integrationKeys.all, "crm"] as const,
};

// ── Queries ─────────────────────────────────────────────────

export function useCrmIntegrations(tenantId?: string) {
  return useQuery<CrmIntegrationListResponse>({
    queryKey: [...integrationKeys.crm(), tenantId],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tenantId) params.set("tenant_id", tenantId);
      const qs = params.toString();
      try {
        const res = await fetchWithAuth(`/api/v1/integrations/external-nodes${qs ? `?${qs}` : ""}`);
        if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
        if (!res.ok) return { integrations: [], total: 0 } as CrmIntegrationListResponse;
        return res.json();
      } catch (err) {
        if ((err as Error).message === "Unauthorized") throw err;
        return { integrations: [], total: 0 } as CrmIntegrationListResponse;
      }
    },
  });
}

// ── Mutations ────────────────────────────────────────────────

export function useInitiateZohoOAuth() {
  return useMutation<ZohoInitiateResponse, Error, { dataCenter?: ZohoDataCenter; tenantId?: string }>({
    mutationFn: async ({ dataCenter = "in", tenantId }) => {
      const params = new URLSearchParams();
      params.set("data_center", dataCenter);
      if (tenantId) params.set("tenant_id", tenantId);
      const res = await fetchWithAuth(
        `/api/v1/integrations/external-nodes/node-z/spawn?${params.toString()}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error("Failed to initiate Zoho OAuth");
      return res.json();
    },
    onSuccess: ({ auth_url }) => {
      // Navigate the current tab to the Zoho authorization page
      window.location.href = auth_url;
    },
  });
}

export function useInitiateHubSpotOAuth() {
  return useMutation<ZohoInitiateResponse, Error, { tenantId?: string }>({
    mutationFn: async ({ tenantId }) => {
      // Stub for HubSpot
      return { auth_url: "#" };
    },
  });
}

export function useInitiateSalesforceOAuth() {
  return useMutation<ZohoInitiateResponse, Error, { tenantId?: string }>({
    mutationFn: async ({ tenantId }) => {
      // Stub for Salesforce
      return { auth_url: "#" };
    },
  });
}

export function useSyncIntegration(tenantId?: string) {
  const queryClient = useQueryClient();
  return useMutation<ZohoSyncResponse, Error, { integrationId: string }>({
    mutationFn: async ({ integrationId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/integrations/external-nodes/${integrationId}/pulse${qs}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error("Failed to sync integration");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.crm() });
    },
  });
}

export function useDisconnectIntegration(tenantId?: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { integrationId: string }>({
    mutationFn: async ({ integrationId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/integrations/external-nodes/${integrationId}${qs}`,
        { method: "DELETE" },
      );
      if (!res.ok) throw new Error("Failed to disconnect integration");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.crm() });
    },
  });
}

// ── Tenant Integration query keys ───────────────────────────

export const tenantIntegrationKeys = {
  all: ["tenant-integrations"] as const,
  list: (tenantId?: string) => [...tenantIntegrationKeys.all, "list", tenantId] as const,
  detail: (id: string) => [...tenantIntegrationKeys.all, "detail", id] as const,
};

// ── Tenant Integration queries ───────────────────────────────

export function useTenantIntegrations(tenantId?: string) {
  return useQuery<TenantIntegrationListResponse>({
    queryKey: tenantIntegrationKeys.list(tenantId),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tenantId) params.set("tenant_id", tenantId);
      const qs = params.toString();
      try {
        const res = await fetchWithAuth(`/api/v1/integrations/access-sigs${qs ? `?${qs}` : ""}`);
        if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
        if (!res.ok) return { integrations: [], total: 0 } as TenantIntegrationListResponse;
        return res.json();
      } catch (err) {
        if ((err as Error).message === "Unauthorized") throw err;
        return { integrations: [], total: 0 } as TenantIntegrationListResponse;
      }
    },
  });
}

// ── Tenant Integration mutations ─────────────────────────────

export function useCreateTenantIntegration() {
  const queryClient = useQueryClient();
  return useMutation<TenantIntegration, Error, TenantIntegrationCreate>({
    mutationFn: async (body) => {
      const res = await fetchWithAuth("/api/v1/integrations/access-sigs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? "Failed to create integration");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantIntegrationKeys.all });
    },
  });
}

export function useUpdateTenantIntegration(id: string) {
  const queryClient = useQueryClient();
  return useMutation<TenantIntegration, Error, TenantIntegrationUpdate>({
    mutationFn: async (body) => {
      const res = await fetchWithAuth(`/api/v1/integrations/access-sigs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? "Failed to update integration");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantIntegrationKeys.all });
    },
  });
}

export function useDeleteTenantIntegration() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { id: string }>({
    mutationFn: async ({ id }) => {
      const res = await fetchWithAuth(`/api/v1/integrations/access-sigs/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete integration");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantIntegrationKeys.all });
    },
  });
}

