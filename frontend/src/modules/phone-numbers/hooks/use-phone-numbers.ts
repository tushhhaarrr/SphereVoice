/**
 * Phone Numbers module — TanStack Query hooks.
 *
 * Uses fetchWithAuth (next-auth/react getSession()) for client-side auth,
 * consistent with calls and agents hooks.
 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  PhoneNumber,
  PhoneNumberAssignRequest,
  PhoneNumberListParams,
  PhoneNumberListResponse,
  PhoneNumberPurchaseRequest,
  PhoneNumberSearchParams,
  PhoneNumberSearchResponse,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

const PHONE_NUMBERS_KEY = "phone-numbers";

// ── List phone numbers ──────────────────────────────────────

export function usePhoneNumbers(params?: PhoneNumberListParams) {
  return useQuery<PhoneNumberListResponse>({
    queryKey: [PHONE_NUMBERS_KEY, params],
    queryFn: async () => {
      const sp = new URLSearchParams();
      if (params?.page) sp.set("page", String(params.page));
      if (params?.limit) sp.set("limit", String(params.limit));
      if (params?.status) sp.set("status", params.status);
      if (params?.agent_id) sp.set("agent_id", params.agent_id);
      if (params?.tenant_id) sp.set("tenant_id", params.tenant_id);
      const qs = sp.toString() ? `?${sp.toString()}` : "";

      const res = await fetchWithAuth(`/api/v1/phone-numbers${qs}`);
      if (!res.ok) throw new Error("Failed to fetch phone numbers");
      return res.json();
    },
  });
}

// ── Search available numbers ────────────────────────────────

export function useSearchAvailableNumbers(
  params: PhoneNumberSearchParams,
  enabled = false,
) {
  return useQuery<PhoneNumberSearchResponse>({
    queryKey: [PHONE_NUMBERS_KEY, "search", params],
    queryFn: async () => {
      const sp = new URLSearchParams();
      if (params.country) sp.set("country", params.country);
      if (params.area_code) sp.set("area_code", params.area_code);
      if (params.contains) sp.set("contains", params.contains);
      if (params.limit) sp.set("limit", String(params.limit));
      if (params.provider) sp.set("provider", params.provider);

      const res = await fetchWithAuth(
        `/api/v1/phone-numbers/search?${sp.toString()}`,
      );
      if (!res.ok) throw new Error("Failed to search available numbers");
      return res.json();
    },
    enabled,
  });
}

// ── Purchase number ─────────────────────────────────────────

export function usePurchaseNumber() {
  const queryClient = useQueryClient();

  return useMutation<PhoneNumber, Error, PhoneNumberPurchaseRequest>({
    mutationFn: async (data) => {
      const res = await fetchWithAuth("/api/v1/phone-numbers/purchase", {
        method: "POST",
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          (err as Record<string, Record<string, string>>)?.error?.message ||
          "Failed to purchase number",
        );
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PHONE_NUMBERS_KEY] });
    },
  });
}

// ── Assign agent ────────────────────────────────────────────

export function useAssignAgent() {
  const queryClient = useQueryClient();

  return useMutation<
    { id: string; phone_number: string; agent_id: string | null },
    Error,
    { numberId: string; body: PhoneNumberAssignRequest }
  >({
    mutationFn: async ({ numberId, body }) => {
      const res = await fetchWithAuth(
        `/api/v1/phone-numbers/${numberId}/assign`,
        {
          method: "PUT",
          body: JSON.stringify(body),
        },
      );
      if (!res.ok) throw new Error("Failed to assign agent");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PHONE_NUMBERS_KEY] });
    },
  });
}

// ── Release number ──────────────────────────────────────────

export function useReleaseNumber() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: async (numberId) => {
      const res = await fetchWithAuth(
        `/api/v1/phone-numbers/${numberId}`,
        { method: "DELETE" },
      );
      if (!res.ok) throw new Error("Failed to release number");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PHONE_NUMBERS_KEY] });
    },
  });
}

// ── Sync Plivo numbers ──────────────────────────────────────

export function useSyncPlivoNumbers() {
  const queryClient = useQueryClient();

  return useMutation<
    { imported: PhoneNumber[]; imported_count: number },
    Error
  >({
    mutationFn: async () => {
      const res = await fetchWithAuth("/api/v1/phone-numbers/sync/plivo", {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          (err as Record<string, Record<string, string>>)?.error?.message ||
          "Failed to sync Plivo numbers",
        );
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PHONE_NUMBERS_KEY] });
    },
  });
}

// ── Set / clear default outbound ────────────────────────────

export function useSetDefaultOutbound() {
  const queryClient = useQueryClient();

  return useMutation<PhoneNumber, Error, string>({
    mutationFn: async (numberId) => {
      const res = await fetchWithAuth(
        `/api/v1/phone-numbers/${numberId}/set-default-outbound`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error("Failed to set default outbound number");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PHONE_NUMBERS_KEY] });
    },
  });
}

export function useClearDefaultOutbound() {
  const queryClient = useQueryClient();

  return useMutation<PhoneNumber, Error, string>({
    mutationFn: async (numberId) => {
      const res = await fetchWithAuth(
        `/api/v1/phone-numbers/${numberId}/clear-default-outbound`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error("Failed to clear default outbound number");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PHONE_NUMBERS_KEY] });
    },
  });
}
