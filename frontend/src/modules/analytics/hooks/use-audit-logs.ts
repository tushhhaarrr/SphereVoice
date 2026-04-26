"use client";

/**
 * Audit log data-fetching hook using TanStack Query.
 */

import { useQuery } from "@tanstack/react-query";
import type { AuditLogListResponse } from "../types";
import { fetchWithAuth } from "@/lib/api-client";

export interface AuditLogParams {
    tenantId?: string;
    userId?: string;
    resourceType?: string;
    action?: string;
    startDate?: string;
    endDate?: string;
    page?: number;
    limit?: number;
    enabled?: boolean;
}

export function useAuditLogs(params?: AuditLogParams) {
    const search = new URLSearchParams();
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    if (params?.userId) search.set("filter_user_id", params.userId);
    if (params?.resourceType) search.set("resource_type", params.resourceType);
    if (params?.action) search.set("action", params.action);
    if (params?.startDate) search.set("start_date", params.startDate);
    if (params?.endDate) search.set("end_date", params.endDate);
    if (params?.page) search.set("page", String(params.page));
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<AuditLogListResponse>({
        queryKey: ["audit-logs", params],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/analytics/audit-logs${qs}`);
            if (!res.ok) throw new Error("Failed to fetch audit logs");
            return res.json();
        },
        enabled: params?.enabled ?? true,
    });
}
