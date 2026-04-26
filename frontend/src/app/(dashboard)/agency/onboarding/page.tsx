"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Building2, BookOpen, Globe } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    getTenantReadinessStage,
    useTenants,
    useSeedWebsiteKB,
    type TenantRecord,
    type TenantReadinessKey,
} from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

const STAGE_ORDER: TenantReadinessKey[] = [
    "needs-activation",
    "needs-team",
    "needs-agent",
    "needs-number",
    "ready",
];

const STAGE_HEADINGS: Record<TenantReadinessKey, string> = {
    "needs-activation": "Needs Activation",
    "needs-team": "Needs Team Setup",
    "needs-agent": "Needs Agent Setup",
    "needs-number": "Needs Phone Number",
    ready: "Ready for Ops",
};

const STAGE_COPY: Record<TenantReadinessKey, string> = {
    "needs-activation": "Tenants that should stay in onboarding until Sphere marks them active.",
    "needs-team": "Invite the first client-facing operator before broader setup work continues.",
    "needs-agent": "The tenant is active, but the actual voice agent configuration is still missing.",
    "needs-number": "The tenant has people and agents but no number provisioned for production traffic.",
    ready: "These tenants have the minimum operating footprint and should be handled through workspaces.",
};

function SeedKBButton({ tenant }: { tenant: TenantRecord }) {
    const seedKB = useSeedWebsiteKB();
    const [open, setOpen] = useState(false);
    const [url, setUrl] = useState("");
    const [done, setDone] = useState(false);

    const hasWebsiteKB = Boolean(tenant.metadata?.website_kb_id);

    const handleSeed = () => {
        if (!url.trim()) return;
        seedKB.mutate(
            { tenantId: tenant.id, website_url: url.trim() },
            {
                onSuccess: () => {
                    setDone(true);
                    setOpen(false);
                    setUrl("");
                },
            },
        );
    };

    return (
        <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) seedKB.reset(); }}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-1.5">
                    <Globe className="h-3.5 w-3.5" />
                    {hasWebsiteKB || done ? "Re-seed KB" : "Seed KB"}
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Seed Knowledge Base from Website</DialogTitle>
                    <DialogDescription>
                        Firecrawl will crawl up to 25 pages and build the tenant KB automatically.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3 pt-2">
                    <Input
                        type="url"
                        placeholder="acme.com or https://acme.com"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSeed()}
                    />
                    {seedKB.error && (
                        <p className="text-xs text-red-500">{seedKB.error.message}</p>
                    )}
                    <Button
                        size="sm"
                        className="w-full"
                        disabled={!url.trim() || seedKB.isPending}
                        onClick={handleSeed}
                    >
                        {seedKB.isPending ? "Queuing..." : "Start Crawl"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function WebsiteKBBadge({ metadata }: { metadata: Record<string, unknown> }) {
    if (!metadata?.website_kb_id) return null;
    return (
        <span
            title={`Website KB seeded from ${metadata.website_url ?? "website"}`}
            className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200"
        >
            <BookOpen className="h-3 w-3" />
            Website KB
        </span>
    );
}

function matchesSearch(tenant: TenantRecord, search: string): boolean {
    const value = search.trim().toLowerCase();
    if (!value) {
        return true;
    }

    return [tenant.name, tenant.slug, tenant.id]
        .join(" ")
        .toLowerCase()
        .includes(value);
}

export default function AgencyOnboardingPage() {
    const { isAdmin, isLoading } = useAuth();
    const [search, setSearch] = useState("");
    const tenants = useTenants({ enabled: isAdmin && !isLoading, limit: 100 });

    if (!isLoading && !isAdmin) {
        return (
            <div className="space-y-6 p-8">
                <Card>
                    <CardHeader>
                        <CardTitle>Admin Access Required</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        Agency onboarding is restricted to Sphere admins.
                    </CardContent>
                </Card>
            </div>
        );
    }

    const filteredTenants = (tenants.data?.tenants ?? [])
        .filter((tenant) => matchesSearch(tenant, search))
        .sort((left, right) => {
            const leftStage = getTenantReadinessStage(left);
            const rightStage = getTenantReadinessStage(right);

            if (leftStage.priority !== rightStage.priority) {
                return leftStage.priority - rightStage.priority;
            }

            return right.updated_at.localeCompare(left.updated_at);
        });

    const counts: Record<TenantReadinessKey, number> = {
        "needs-activation": 0,
        "needs-team": 0,
        "needs-agent": 0,
        "needs-number": 0,
        ready: 0,
    };

    filteredTenants.forEach((tenant) => {
        counts[getTenantReadinessStage(tenant).key] += 1;
    });

    return (
        <div className="space-y-6 p-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
                        Agency Operations
                    </p>
                    <div>
                        <h1 className="text-2xl font-bold">Onboarding Queue</h1>
                        <p className="mt-1 max-w-3xl text-muted-foreground">
                            Work the client portfolio by readiness stage. Tenants should move from onboarding into
                            workspaces only after the minimum operator, agent, and number setup is complete.
                        </p>
                    </div>
                </div>
                <Button asChild variant="outline">
                    <Link href="/agency/tenants">Open Tenant Directory</Link>
                </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                {STAGE_ORDER.map((key) => (
                    <Card key={key}>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">{STAGE_HEADINGS[key]}</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-semibold tracking-tight">{counts[key]}</div>
                            <p className="mt-2 text-sm text-muted-foreground">{STAGE_COPY[key]}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <Card>
                <CardHeader className="gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <CardTitle>Staged Tenant Queue</CardTitle>
                        <p className="mt-1 text-sm text-muted-foreground">
                            The queue is ordered to surface incomplete tenants before operators jump into execution.
                        </p>
                    </div>
                    <div className="w-full max-w-sm">
                        <Input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Filter by tenant name, slug, or ID..."
                        />
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {tenants.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, index) => (
                                <div key={index} className="h-24 animate-pulse rounded-lg bg-muted" />
                            ))}
                        </div>
                    ) : filteredTenants.length === 0 ? (
                        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                            No tenants matched the current onboarding filter.
                        </div>
                    ) : (
                        STAGE_ORDER.map((key) => {
                            const stageTenants = filteredTenants.filter(
                                (tenant) => getTenantReadinessStage(tenant).key === key,
                            );

                            if (stageTenants.length === 0) {
                                return null;
                            }

                            return (
                                <section key={key} className="space-y-3">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <h2 className="text-lg font-semibold tracking-tight">{STAGE_HEADINGS[key]}</h2>
                                            <p className="text-sm text-muted-foreground">{STAGE_COPY[key]}</p>
                                        </div>
                                        <Badge variant="outline">{stageTenants.length} tenants</Badge>
                                    </div>

                                    <div className="grid gap-3 xl:grid-cols-2">
                                        {stageTenants.map((tenant) => {
                                            const stage = getTenantReadinessStage(tenant);
                                            const plan = tenant.metadata.plan;
                                            const planLabel =
                                                typeof plan === "string" && plan.trim() ? plan : "Unassigned plan";

                                            return (
                                                <Card key={tenant.id} className="border-l-4 border-l-muted-foreground/20">
                                                    <CardContent className="space-y-4 p-5">
                                                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                                            <div className="space-y-2">
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    <Building2 className="h-4 w-4 text-muted-foreground" />
                                                                    <h3 className="text-base font-semibold">{tenant.name}</h3>
                                                                    <Badge variant="outline" className={stage.badgeClassName}>
                                                                        {stage.label}
                                                                    </Badge>
                                                                    <WebsiteKBBadge metadata={tenant.metadata} />
                                                                </div>
                                                                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                                                                    <span className="rounded-full bg-muted px-3 py-1">{tenant.slug}</span>
                                                                    <span className="rounded-full bg-muted px-3 py-1">Plan: {planLabel}</span>
                                                                    <span className="rounded-full bg-muted px-3 py-1">
                                                                        Updated {new Date(tenant.updated_at).toLocaleDateString()}
                                                                    </span>
                                                                </div>
                                                                <p className="max-w-2xl text-sm text-muted-foreground">{stage.detail}</p>
                                                            </div>

                                                            <div className="flex flex-wrap gap-2">
                                                                <SeedKBButton tenant={tenant} />
                                                                <Button asChild variant="outline" size="sm">
                                                                    <Link href={`/workspace/${tenant.id}/overview`}>Open Workspace</Link>
                                                                </Button>
                                                            </div>
                                                        </div>

                                                        <div className="grid gap-3 sm:grid-cols-4">
                                                            <div className="rounded-lg bg-muted/60 p-3">
                                                                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Users</p>
                                                                <p className="mt-2 text-2xl font-semibold">{tenant.summary.user_count}</p>
                                                            </div>
                                                            <div className="rounded-lg bg-muted/60 p-3">
                                                                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Agents</p>
                                                                <p className="mt-2 text-2xl font-semibold">{tenant.summary.agent_count}</p>
                                                            </div>
                                                            <div className="rounded-lg bg-muted/60 p-3">
                                                                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Numbers</p>
                                                                <p className="mt-2 text-2xl font-semibold">{tenant.summary.phone_number_count}</p>
                                                            </div>
                                                            <div className="rounded-lg bg-muted/60 p-3">
                                                                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Calls</p>
                                                                <p className="mt-2 text-2xl font-semibold">{tenant.summary.call_count}</p>
                                                            </div>
                                                        </div>

                                                        <div className="flex items-center justify-between gap-3 border-t pt-4 text-sm text-muted-foreground">
                                                            <span>Tenant ID {tenant.id.slice(0, 8)}...</span>
                                                            <Link
                                                                href={`/workspace/${tenant.id}/overview`}
                                                                className="inline-flex items-center gap-1 font-medium text-foreground"
                                                            >
                                                                Continue in workspace
                                                                <ArrowRight className="h-4 w-4" />
                                                            </Link>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            );
                                        })}
                                    </div>
                                </section>
                            );
                        })
                    )}
                </CardContent>
            </Card>
        </div>
    );
}