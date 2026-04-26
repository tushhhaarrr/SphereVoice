"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
    ArrowRight,
    Bot,
    Megaphone,
    Phone,
    PhoneCall,
    Users,
    Workflow,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTenantReadinessStage, useTenants } from "@/modules/analytics";
import type { TenantRecord } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

export default function DashboardPage() {
    const { user, isAdmin, isLoading } = useAuth();
    const tenants = useTenants({
        enabled: isAdmin && !isLoading,
        limit: 100,
    });

    // Non-admin with tenant — quick links to their workspace
    if (!isLoading && !isAdmin && user?.tenantId) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
                    <p className="text-sm text-muted-foreground">
                        Welcome back. Jump into your workspace.
                    </p>
                </div>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <QuickLink
                        href="/agents"
                        icon={Bot}
                        title="Agents"
                        description="Manage your voice agents"
                    />
                    <QuickLink
                        href="/campaigns"
                        icon={Megaphone}
                        title="Campaigns"
                        description="Run outbound campaigns"
                    />
                    <QuickLink
                        href="/phone-numbers"
                        icon={Phone}
                        title="Phone Numbers"
                        description="Manage your numbers"
                    />
                </div>
            </div>
        );
    }

    if (!isLoading && !isAdmin) {
        return (
            <div className="space-y-6 p-8">
                <Card>
                    <CardHeader>
                        <CardTitle>Access Required</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        You need a tenant assignment to access the dashboard. Contact your admin.
                    </CardContent>
                </Card>
            </div>
        );
    }

    // Admin — portfolio overview
    const portfolio = useMemo(() => {
        const items = (tenants.data?.tenants ?? []).map((tenant) => ({
            tenant,
            readiness: getTenantReadinessStage(tenant),
        }));

        const needsAgent = items.filter((i) => i.readiness.key === "needs-agent");
        const needsNumber = items.filter((i) => i.readiness.key === "needs-number");
        const ready = items.filter((i) => i.readiness.key === "ready");

        return {
            items,
            needsAgent,
            needsNumber,
            ready,
            totalAgents: items.reduce((s, i) => s + i.tenant.summary.agent_count, 0),
        };
    }, [tenants.data]);

    return (
        <div className="space-y-8 p-8">
            <section className="rounded-2xl border bg-card p-6 shadow-sm">
                <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div className="space-y-3">
                        <div className="inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                            Agency Command
                        </div>
                        <div>
                            <h1 className="text-3xl font-semibold tracking-tight">
                                Portfolio Overview
                            </h1>
                            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                                See which clients need attention. Use tenant workspaces for
                                editing, publishing, and day-to-day operations.
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <Button asChild>
                            <Link href="/agency/tenants">Tenant Directory</Link>
                        </Button>
                        <Button asChild variant="outline">
                            <Link href="/agency/onboarding">Onboarding Queue</Link>
                        </Button>
                    </div>
                </div>
            </section>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatCard
                    title="Needs Agent Setup"
                    value={portfolio.needsAgent.length}
                    detail="Clients with no configured agent"
                    icon={Workflow}
                />
                <StatCard
                    title="Needs Phone Number"
                    value={portfolio.needsNumber.length}
                    detail="Ready for telephony provisioning"
                    icon={PhoneCall}
                />
                <StatCard
                    title="Ready / Live"
                    value={portfolio.ready.length}
                    detail="Core setup in place"
                    icon={Users}
                />
                <StatCard
                    title="Total Agents"
                    value={portfolio.totalAgents}
                    detail="Across all tenants"
                    icon={Bot}
                />
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Client Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {tenants.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <div key={i} className="h-20 animate-pulse rounded-xl bg-muted" />
                            ))}
                        </div>
                    ) : portfolio.items.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No tenants yet.</p>
                    ) : (
                        portfolio.items
                            .slice()
                            .sort((a, b) => a.readiness.priority - b.readiness.priority)
                            .map(({ tenant, readiness }) => (
                                <TenantRow
                                    key={tenant.id}
                                    tenant={tenant}
                                    label={readiness.label}
                                    detail={readiness.detail}
                                    href={`/workspace/${tenant.id}/agents`}
                                />
                            ))
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function StatCard({
    title,
    value,
    detail,
    icon: Icon,
}: {
    title: string;
    value: number;
    detail: string;
    icon: React.ComponentType<{ className?: string }>;
}) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-semibold">{value}</div>
                <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
            </CardContent>
        </Card>
    );
}

function TenantRow({
    tenant,
    label,
    detail,
    href,
}: {
    tenant: TenantRecord;
    label: string;
    detail: string;
    href: string;
}) {
    return (
        <div className="flex flex-col gap-4 rounded-xl border p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
                <div>
                    <p className="font-medium text-foreground">{tenant.name}</p>
                    <p className="text-sm text-muted-foreground">{tenant.slug}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span className="rounded-full border px-2.5 py-1">{label}</span>
                    <span className="rounded-full border px-2.5 py-1">
                        Users {tenant.summary.user_count}
                    </span>
                    <span className="rounded-full border px-2.5 py-1">
                        Agents {tenant.summary.agent_count}
                    </span>
                    <span className="rounded-full border px-2.5 py-1">
                        Numbers {tenant.summary.phone_number_count}
                    </span>
                </div>
                <p className="text-sm text-muted-foreground">{detail}</p>
            </div>

            <Button asChild variant="outline">
                <Link href={href}>
                    Open Workspace
                    <ArrowRight className="h-4 w-4" />
                </Link>
            </Button>
        </div>
    );
}

function QuickLink({
    href,
    icon: Icon,
    title,
    description,
}: {
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    title: string;
    description: string;
}) {
    return (
        <Link href={href}>
            <Card className="transition-colors hover:border-primary/50">
                <CardHeader className="flex flex-row items-center gap-3 pb-2">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                    <CardTitle className="text-base">{title}</CardTitle>
                </CardHeader>
                <CardContent className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{description}</span>
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </CardContent>
            </Card>
        </Link>
    );
}
