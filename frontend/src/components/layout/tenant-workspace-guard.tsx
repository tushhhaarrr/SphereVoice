"use client";

import { useEffect } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";

interface TenantWorkspaceGuardProps {
    tenantId: string;
}

const WORKSPACE_QUERY_ROOTS = new Set([
    "agents",
    "agent-versions",
    "analytics",
    "audit-logs",
    "calls",
    "knowledge-bases",
    "phone-numbers",
    "providers",
    "templates",
    "users",
    "webhooks",
    "webhook-deliveries",
]);

let activeWorkspaceTenantId: string | null = null;

function isTenantSensitiveQuery(queryKey: QueryKey): boolean {
    const root = queryKey[0];
    return typeof root === "string" && WORKSPACE_QUERY_ROOTS.has(root);
}

export function TenantWorkspaceGuard({ tenantId }: TenantWorkspaceGuardProps) {
    const queryClient = useQueryClient();

    useEffect(() => {
        if (activeWorkspaceTenantId && activeWorkspaceTenantId !== tenantId) {
            void queryClient.cancelQueries({
                predicate: (query) => isTenantSensitiveQuery(query.queryKey),
            });
            queryClient.removeQueries({
                predicate: (query) => isTenantSensitiveQuery(query.queryKey),
            });
        }

        activeWorkspaceTenantId = tenantId;
    }, [queryClient, tenantId]);

    return null;
}