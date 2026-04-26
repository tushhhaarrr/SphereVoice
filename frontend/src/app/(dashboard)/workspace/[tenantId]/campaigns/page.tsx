"use client";

import { useParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenant } from "@/modules/analytics";
import { CampaignList } from "@/modules/campaigns";
import { useAuth } from "@/modules/auth";

export default function TenantWorkspaceCampaignsPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { isAdmin, isLoading } = useAuth();
    const tenant = useTenant(tenantId, isAdmin && !isLoading);

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Campaign Scope</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-muted-foreground">
                    <p>
                        This workspace only shows campaigns owned by {tenant.data?.name ?? "this tenant"}.
                    </p>
                    <p>
                        Manage outbound voice campaigns, track progress, and review call outcomes here.
                    </p>
                </CardContent>
            </Card>

            <CampaignList tenantId={tenantId} />
        </div>
    );
}
