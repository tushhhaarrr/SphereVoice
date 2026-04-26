"use client";

/**
 * Webhook data-fetching hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
    Webhook,
    WebhookCreateRequest,
    WebhookDeliveryListResponse,
    WebhookListResponse,
    WebhookReplayResponse,
    WebhookUpdateRequest,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── Queries ─────────────────────────────────────────────────

export function useWebhooks(params?: { page?: number; limit?: number }) {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<WebhookListResponse>({
        queryKey: ["webhooks", params],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/webhooks${qs}`);
            if (!res.ok) throw new Error("Failed to fetch webhooks");
            return res.json();
        },
    });
}

export function useWebhook(id: string) {
    return useQuery<Webhook>({
        queryKey: ["webhooks", id],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/webhooks/${id}`);
            if (!res.ok) throw new Error("Failed to fetch webhook");
            return res.json();
        },
        enabled: !!id,
    });
}

export function useWebhookDeliveries(params?: {
    webhookId?: string;
    status?: string;
    page?: number;
    limit?: number;
}) {
    const search = new URLSearchParams();
    if (params?.webhookId) search.set("webhook_id", params.webhookId);
    if (params?.status) search.set("status", params.status);
    if (params?.page) search.set("page", String(params.page));
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<WebhookDeliveryListResponse>({
        queryKey: ["webhook-deliveries", params],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/webhooks/deliveries${qs}`);
            if (!res.ok) throw new Error("Failed to fetch deliveries");
            return res.json();
        },
    });
}

// ── Mutations ───────────────────────────────────────────────

export function useCreateWebhook() {
    const queryClient = useQueryClient();

    return useMutation<Webhook, Error, WebhookCreateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/webhooks", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to create webhook");
            }
            return res.json();
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
        },
    });
}

export function useUpdateWebhook() {
    const queryClient = useQueryClient();

    return useMutation<Webhook, Error, { id: string; data: WebhookUpdateRequest }>({
        mutationFn: async ({ id, data }) => {
            const res = await fetchWithAuth(`/api/v1/webhooks/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to update webhook");
            }
            return res.json();
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
        },
    });
}

export function useDeleteWebhook() {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/webhooks/${id}`, {
                method: "DELETE",
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to delete webhook");
            }
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
        },
    });
}

export function useReplayDelivery() {
    const queryClient = useQueryClient();

    return useMutation<WebhookReplayResponse, Error, string>({
        mutationFn: async (deliveryId) => {
            const res = await fetchWithAuth(
                `/api/v1/webhooks/deliveries/${deliveryId}/replay`,
                { method: "POST" },
            );
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to replay delivery");
            }
            return res.json();
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["webhook-deliveries"] });
        },
    });
}
