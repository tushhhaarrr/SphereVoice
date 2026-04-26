"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

import { AuditLogTable, useAuditLogs } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

export default function TenantWorkspaceActivityPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { isAdmin, isLoading } = useAuth();
    const [page, setPage] = useState(1);
    const [resourceTypeFilter, setResourceTypeFilter] = useState("all");
    const [actionFilter, setActionFilter] = useState("all");

    const auditLogs = useAuditLogs({
        tenantId,
        resourceType: resourceTypeFilter !== "all" ? resourceTypeFilter : undefined,
        action: actionFilter !== "all" ? actionFilter : undefined,
        page,
        limit: 50,
        enabled: isAdmin && !isLoading,
    });

    return (
        <div className="space-y-4">
            <div>
                <h2 className="text-xl font-semibold">Tenant Activity</h2>
                <p className="text-sm text-muted-foreground">
                    Audit visibility is scoped to this tenant workspace to reduce cross-client investigation mistakes.
                </p>
            </div>

            <AuditLogTable
                data={auditLogs.data}
                isLoading={auditLogs.isLoading}
                page={page}
                onPageChange={setPage}
                resourceTypeFilter={resourceTypeFilter}
                onResourceTypeChange={(value) => {
                    setResourceTypeFilter(value);
                    setPage(1);
                }}
                actionFilter={actionFilter}
                onActionChange={(value) => {
                    setActionFilter(value);
                    setPage(1);
                }}
            />
        </div>
    );
}