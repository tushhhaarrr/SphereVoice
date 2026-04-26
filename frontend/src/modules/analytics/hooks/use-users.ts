"use client";

/**
 * User management data-fetching hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
    InvitationListResponse,
    UserInviteRequest,
    UserInviteSentResponse,
    UserListResponse,
    UserProfile,
    UserUpdateRequest,
} from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998";

async function fetchWithAuth(
    path: string,
    init?: RequestInit
): Promise<Response> {
    const { getSession } = await import("next-auth/react");
    const session = await getSession();

    const headers: HeadersInit = {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
    };

    if (session?.accessToken) {
        (headers as Record<string, string>)["Authorization"] =
            `Bearer ${session.accessToken}`;
    }

    return fetch(`${API_BASE}${path}`, { ...init, headers });
}

// ── Queries ─────────────────────────────────────────────────

export function useUsers(params?: {
    tenantId?: string;
    role?: string;
    isActive?: boolean;
    search?: string;
    page?: number;
    limit?: number;
    enabled?: boolean;
}) {
    const search = new URLSearchParams();
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    if (params?.role) search.set("role", params.role);
    if (params?.isActive !== undefined)
        search.set("is_active", String(params.isActive));
    if (params?.search) search.set("search", params.search);
    if (params?.page) search.set("page", String(params.page));
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<UserListResponse>({
        queryKey: ["users", params],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/analytics/users${qs}`);
            if (!res.ok) throw new Error("Failed to fetch users");
            return res.json();
        },
        enabled: params?.enabled ?? true,
    });
}

// ── Mutations ───────────────────────────────────────────────

export function useInviteUser() {
    const queryClient = useQueryClient();

    return useMutation<UserInviteSentResponse, Error, UserInviteRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/analytics/users/invite", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail?.error?.message || err.error?.message || "Failed to invite user");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["users"] });
        },
    });
}

export function useUpdateUser() {
    const queryClient = useQueryClient();

    return useMutation<
        UserProfile,
        Error,
        { userId: string; data: UserUpdateRequest }
    >({
        mutationFn: async ({ userId, data }) => {
            const res = await fetchWithAuth(`/api/v1/analytics/users/${userId}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to update user");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["users"] });
        },
    });
}

export function useInvitations() {
    return useQuery<InvitationListResponse>({
        queryKey: ["invitations"],
        queryFn: async () => {
            const res = await fetchWithAuth("/api/v1/analytics/users/invites");
            if (!res.ok) throw new Error("Failed to fetch invitations");
            return res.json();
        },
    });
}

export function useRevokeInvitation() {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (invitationId) => {
            const res = await fetchWithAuth(
                `/api/v1/analytics/users/invites/${invitationId}`,
                { method: "DELETE" }
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.error?.message || "Failed to revoke invitation");
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["invitations"] });
        },
    });
}
