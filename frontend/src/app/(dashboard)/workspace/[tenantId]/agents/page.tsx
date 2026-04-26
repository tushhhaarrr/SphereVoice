"use client";

import { useParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenant } from "@/modules/analytics";
import { AgentList } from "@/modules/agents";
import { useAuth } from "@/modules/auth";

export default function TenantWorkspaceAgentsPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { isAdmin, isLoading } = useAuth();
    const tenant = useTenant(tenantId, isAdmin && !isLoading);

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Agent Scope</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-muted-foreground">
                    <p>
                        This workspace only shows agents owned by {tenant.data?.name ?? "this tenant"}.
                    </p>
                    <p>
                        Keep agent review, publishing, and destructive actions inside the tenant workspace to reduce cross-client mistakes.
                    </p>
                </CardContent>
            </Card>

            <AgentList tenantId={tenantId} tenantName={tenant.data?.name} />
        </div>
    );
}