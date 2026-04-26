"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenant } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

export default function TenantWorkspaceOverviewPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { isAdmin, isLoading } = useAuth();
    const tenant = useTenant(tenantId, isAdmin && !isLoading);
    const summary = tenant.data?.summary;

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Card>
                    <CardHeader>
                        <CardTitle>Users</CardTitle>
                    </CardHeader>
                    <CardContent className="text-3xl font-semibold">{summary?.user_count ?? 0}</CardContent>
                </Card>
                <Card>
                    <CardHeader>
                        <CardTitle>Agents</CardTitle>
                    </CardHeader>
                    <CardContent className="text-3xl font-semibold">{summary?.agent_count ?? 0}</CardContent>
                </Card>
                <Card>
                    <CardHeader>
                        <CardTitle>Calls</CardTitle>
                    </CardHeader>
                    <CardContent className="text-3xl font-semibold">{summary?.call_count ?? 0}</CardContent>
                </Card>
                <Card>
                    <CardHeader>
                        <CardTitle>Numbers</CardTitle>
                    </CardHeader>
                    <CardContent className="text-3xl font-semibold">{summary?.phone_number_count ?? 0}</CardContent>
                </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
                <Card>
                    <CardHeader>
                        <CardTitle>Operational Guidance</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm text-muted-foreground">
                        <p>
                            This workspace is the isolation boundary for client-specific actions. Operators should complete edits,
                            invites, and reviews here rather than from the global agency layer.
                        </p>
                        <div className="flex flex-wrap gap-2">
                            <Button asChild>
                                <Link href={`/workspace/${tenantId}/users`}>Manage Users</Link>
                            </Button>
                            <Button asChild variant="outline">
                                <Link href={`/workspace/${tenantId}/agents`}>Manage Agents</Link>
                            </Button>
                            <Button asChild variant="outline">
                                <Link href={`/workspace/${tenantId}/activity`}>View Activity</Link>
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Onboarding State</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm text-muted-foreground">
                        <p>Phase 1 creates the isolated workspace shell.</p>
                        <p>Next phases should add owner assignment, onboarding checklist, approvals, and setup progress.</p>
                        <p>Current tenant status: {tenant.data?.status ?? "loading"}</p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}