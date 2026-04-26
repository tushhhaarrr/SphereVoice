"use client";

import Link from "next/link";
import { ArrowRight, Megaphone } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenants } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";
import { CampaignList } from "@/modules/campaigns";

export default function CampaignsPage() {
    const { user, isAdmin, isLoading } = useAuth();
    const tenants = useTenants({
        enabled: isAdmin && !isLoading,
        limit: 100,
    });

    // Non-admin users with a tenant — show their campaigns directly
    if (!isLoading && !isAdmin && user?.tenantId) {
        return (
            <div className="space-y-6">
                <CampaignList tenantId={user.tenantId} />
            </div>
        );
    }

    // Admin — show per-tenant campaign overview
    const tenantList = tenants.data?.tenants ?? [];

    if (!isLoading && !isAdmin) {
        return (
            <div className="space-y-6 p-8">
                <Card>
                    <CardHeader>
                        <CardTitle>Access Required</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        Campaigns require a tenant assignment. Contact your admin.
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Campaigns</h1>
                    <p className="text-sm text-muted-foreground">
                        Outbound voice campaigns across all tenants
                    </p>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {tenantList.map((tenant) => (
                    <Link
                        key={tenant.id}
                        href={`/workspace/${tenant.id}/campaigns`}
                    >
                        <Card className="transition-colors hover:border-primary/50">
                            <CardHeader className="flex flex-row items-center gap-3 pb-2">
                                <Megaphone className="h-5 w-5 text-muted-foreground" />
                                <CardTitle className="text-base">{tenant.name}</CardTitle>
                            </CardHeader>
                            <CardContent className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">
                                    View campaigns
                                </span>
                                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                            </CardContent>
                        </Card>
                    </Link>
                ))}
            </div>

            {!isLoading && tenantList.length === 0 && (
                <Card>
                    <CardContent className="py-8 text-center text-sm text-muted-foreground">
                        No tenants found. Create a tenant first to set up campaigns.
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
