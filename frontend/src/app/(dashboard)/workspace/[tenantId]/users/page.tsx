"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

import { UsersTable, useTenant, useUsers } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

export default function TenantWorkspaceUsersPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { isAdmin, isLoading } = useAuth();
    const [search, setSearch] = useState("");
    const users = useUsers({
        tenantId,
        search: search || undefined,
        page: 1,
        limit: 50,
        enabled: isAdmin && !isLoading,
    });
    const tenant = useTenant(tenantId, isAdmin && !isLoading);

    return (
        <div className="space-y-4">
            <div>
                <h2 className="text-xl font-semibold">Workspace Users</h2>
                <p className="text-sm text-muted-foreground">
                    All invitations and user edits here are constrained to {tenant.data?.name ?? "this tenant"}.
                </p>
            </div>

            <UsersTable
                data={users.data}
                isLoading={users.isLoading}
                searchValue={search}
                onSearchChange={setSearch}
                tenantOptions={tenant.data ? [tenant.data] : []}
            />
        </div>
    );
}