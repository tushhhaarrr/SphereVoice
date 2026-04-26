"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useTenant } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

interface TenantWorkspaceShellProps {
    tenantId: string;
    children: React.ReactNode;
}

const WORKSPACE_NAV = [
    { label: "Overview", href: (tenantId: string) => `/workspace/${tenantId}/overview` },
    { label: "Agents", href: (tenantId: string) => `/workspace/${tenantId}/agents` },
    { label: "Users", href: (tenantId: string) => `/workspace/${tenantId}/users` },
    { label: "Activity", href: (tenantId: string) => `/workspace/${tenantId}/activity` },
    { label: "Phone Numbers", href: (tenantId: string) => `/workspace/${tenantId}/phone-numbers` },
    { label: "Providers", href: (tenantId: string) => `/workspace/${tenantId}/providers` },
    { label: "Knowledge Base", href: (tenantId: string) => `/workspace/${tenantId}/knowledge-base` },
    { label: "Campaigns", href: (tenantId: string) => `/workspace/${tenantId}/campaigns` },
    { label: "Integrations", href: (tenantId: string) => `/workspace/${tenantId}/integrations` },
];

function isActivePath(pathname: string, href: string): boolean {
    return pathname === href || pathname.startsWith(`${href}/`);
}

export function TenantWorkspaceShell({ tenantId, children }: TenantWorkspaceShellProps) {
    const pathname = usePathname();
    const { isAdmin, isLoading } = useAuth();
    const tenant = useTenant(tenantId, isAdmin && !isLoading);
    const plan = tenant.data?.metadata?.plan;
    const planLabel = typeof plan === "string" && plan.trim() ? plan : "Unassigned plan";
    const isFullscreenAgentEditor = /^\/workspace\/[^/]+\/agents\/[^/]+$/.test(pathname);

    if (!isLoading && !isAdmin) {
        return (
            <div className="space-y-6">
                <Card>
                    <CardHeader>
                        <CardTitle>Admin Access Required</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        Tenant workspaces are reserved for Sphere operators with admin access.
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (isFullscreenAgentEditor) {
        return (
            <div className={cn("h-full min-h-0 overflow-x-hidden overflow-y-auto", tenant.isLoading && "opacity-80")}>
                {children}
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <section className="rounded-xl border bg-background/95 p-5 shadow-sm backdrop-blur">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                            <span>Tenant Workspace</span>
                            <span className="rounded-full border px-2 py-1 text-[10px] tracking-[0.16em]">
                                {tenant.data?.status ?? "Loading"}
                            </span>
                        </div>
                        <div>
                            <h1 className="text-3xl font-semibold tracking-tight">
                                {tenant.data?.name ?? "Loading tenant..."}
                            </h1>
                            <p className="mt-1 text-sm text-muted-foreground">
                                All actions in this workspace are scoped to this client only.
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span className="rounded-full bg-muted px-3 py-1">Slug: {tenant.data?.slug ?? tenantId}</span>
                            <span className="rounded-full bg-muted px-3 py-1">Plan: {planLabel}</span>
                            <span className="rounded-full bg-muted px-3 py-1">Tenant ID: {tenantId.slice(0, 8)}...</span>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <Button asChild variant="outline">
                            <Link href="/agency/tenants">Back to Tenant Directory</Link>
                        </Button>
                        <Button asChild>
                            <Link href={`/workspace/${tenantId}/users`}>Open Users</Link>
                        </Button>
                    </div>
                </div>

                <nav className="mt-4 flex flex-wrap gap-2 border-t pt-4">
                    {WORKSPACE_NAV.map((item) => {
                        const href = item.href(tenantId);
                        const active = isActivePath(pathname, href);
                        return (
                            <Button key={href} asChild variant={active ? "default" : "outline"} size="sm">
                                <Link href={href}>{item.label}</Link>
                            </Button>
                        );
                    })}
                </nav>
            </section>

            <div className={cn("space-y-6", tenant.isLoading && "opacity-80")}>{children}</div>
        </div>
    );
}