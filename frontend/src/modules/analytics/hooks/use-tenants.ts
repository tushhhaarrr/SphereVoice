"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  TenantCreateRequest,
  TenantListResponse,
  TenantRecord,
  TenantStatus,
  TenantUpdateRequest,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

export interface TenantParams {
  search?: string;
  status?: TenantStatus;
  page?: number;
  limit?: number;
  enabled?: boolean;
}

export function useTenants(params?: TenantParams) {
  const search = new URLSearchParams();
  if (params?.search) search.set("search", params.search);
  if (params?.status) search.set("status", params.status);
  if (params?.page) search.set("page", String(params.page));
  if (params?.limit) search.set("limit", String(params.limit));
  const qs = search.toString() ? `?${search.toString()}` : "";

  return useQuery<TenantListResponse>({
    queryKey: ["tenants", params],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/analytics/tenants${qs}`);
      if (!res.ok) throw new Error("Failed to fetch tenants");
      return res.json();
    },
    enabled: params?.enabled ?? true,
  });
}

export function useTenant(tenantId?: string, enabled = true) {
  return useQuery<TenantRecord>({
    queryKey: ["tenant", tenantId],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/analytics/tenants/${tenantId}`);
      if (!res.ok) throw new Error("Failed to fetch tenant");
      return res.json();
    },
    enabled: Boolean(tenantId) && enabled,
  });
}

export function useCreateTenant() {
  const queryClient = useQueryClient();

  return useMutation<TenantRecord, Error, TenantCreateRequest>({
    mutationFn: async (data) => {
      const res = await fetchWithAuth("/api/v1/analytics/tenants", {
        method: "POST",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json();
        // FastAPI wraps SphereVoice exceptions as { detail: { error: { message } } }
        throw new Error(
          err.detail?.error?.message ||
          err.error?.message ||
          "Failed to create tenant"
        );
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenants"] });
    },
  });
}

export interface SeedWebsiteKBResponse {
  kb_id: string;
  status: string;
}

export function useSeedWebsiteKB() {
  return useMutation<SeedWebsiteKBResponse, Error, { tenantId: string; website_url: string }>({
    mutationFn: async ({ tenantId, website_url }) => {
      // Normalize: prepend https:// if no scheme given (e.g. "acme.com" → "https://acme.com")
      const normalizedUrl =
        /^https?:\/\//i.test(website_url) ? website_url : `https://${website_url}`;

      const res = await fetchWithAuth(
        `/api/v1/analytics/tenants/${tenantId}/seed-website-kb`,
        {
          method: "POST",
          body: JSON.stringify({ website_url: normalizedUrl }),
        },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        // FastAPI HTTPException wraps detail as { detail: { error: { message } } }
        const message =
          err.detail?.error?.message ||
          err.error?.message ||
          "Failed to seed website KB";
        throw new Error(message);
      }
      return res.json();
    },
  });
}

export function useUpdateTenant() {
  const queryClient = useQueryClient();

  return useMutation<TenantRecord, Error, { tenantId: string; data: TenantUpdateRequest }>({
    mutationFn: async ({ tenantId, data }) => {
      const res = await fetchWithAuth(`/api/v1/analytics/tenants/${tenantId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error?.message || "Failed to update tenant");
      }
      return res.json();
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["tenants"] });
      queryClient.invalidateQueries({ queryKey: ["tenant", variables.tenantId] });
    },
  });
}