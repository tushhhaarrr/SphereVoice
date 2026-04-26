"use client";

import { useParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenant } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";
import { ProviderList } from "@/modules/providers";

export default function TenantWorkspaceProvidersPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { isAdmin, isLoading } = useAuth();
    const tenant = useTenant(tenantId, isAdmin && !isLoading);

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Provider Scope</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-muted-foreground">
                    <p>
                        This workspace shows shared defaults alongside keys owned by {tenant.data?.name ?? "this tenant"}.
                    </p>
                    <p>
                        New providers created here are tenant-scoped by default so operators do not accidentally place
                        client credentials into the global pool.
                    </p>
                </CardContent>
            </Card>

            <ProviderList tenantId={tenantId} tenantName={tenant.data?.name} />
        </div>
    );
}