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
      const res = await fetchWithAuth(`/api/v1/integrations/crm${qs ? `?${qs}` : ""}`);
      if (!res.ok) throw new Error("Failed to fetch CRM integrations");
      return res.json();
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
        `/api/v1/integrations/crm/zoho/initiate?${params.toString()}`,
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
      const params = new URLSearchParams();
      if (tenantId) params.set("tenant_id", tenantId);
      const res = await fetchWithAuth(
        `/api/v1/integrations/crm/hubspot/initiate?${params.toString()}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error("Failed to initiate HubSpot OAuth");
      return res.json();
    },
    onSuccess: ({ auth_url }) => {
      window.location.href = auth_url;
    },
  });
}

export function useInitiateSalesforceOAuth() {
  return useMutation<ZohoInitiateResponse, Error, { tenantId?: string }>({
    mutationFn: async ({ tenantId }) => {
      const params = new URLSearchParams();
      if (tenantId) params.set("tenant_id", tenantId);
      const res = await fetchWithAuth(
        `/api/v1/integrations/crm/salesforce/initiate?${params.toString()}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error("Failed to initiate Salesforce OAuth");
      return res.json();
    },
    onSuccess: ({ auth_url }) => {
      window.location.href = auth_url;
    },
  });
}

export function useSyncIntegration(tenantId?: string) {
  const queryClient = useQueryClient();
  return useMutation<ZohoSyncResponse, Error, { integrationId: string }>({
    mutationFn: async ({ integrationId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/integrations/crm/${integrationId}/sync${qs}`,
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
        `/api/v1/integrations/crm/${integrationId}${qs}`,
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
      const res = await fetchWithAuth(`/api/v1/integrations${qs ? `?${qs}` : ""}`);
      if (!res.ok) throw new Error("Failed to fetch tenant integrations");
      return res.json();
    },
  });
}

// ── Tenant Integration mutations ─────────────────────────────

export function useCreateTenantIntegration() {
  const queryClient = useQueryClient();
  return useMutation<TenantIntegration, Error, TenantIntegrationCreate>({
    mutationFn: async (body) => {
      const res = await fetchWithAuth("/api/v1/integrations", {
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
      const res = await fetchWithAuth(`/api/v1/integrations/${id}`, {
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
      const res = await fetchWithAuth(`/api/v1/integrations/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete integration");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tenantIntegrationKeys.all });
    },
  });
}
