"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Plus, Search, Pencil, ArrowRight } from "lucide-react";
import type {
    TenantCreateRequest,
    TenantListResponse,
    TenantRecord,
    TenantStatus,
    TenantUpdateRequest,
} from "../types";
import { getTenantReadinessStage } from "../lib/tenant-readiness";
import { useCreateTenant, useUpdateTenant } from "../hooks/use-tenants";

interface TenantsTableProps {
    data: TenantListResponse | undefined;
    isLoading: boolean;
    searchValue: string;
    onSearchChange: (value: string) => void;
    statusValue: string;
    onStatusChange: (value: string) => void;
}

const STATUS_OPTIONS: TenantStatus[] = ["active", "inactive", "suspended"];

function statusClasses(status: string): string {
    switch (status) {
        case "active":
            return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200";
        case "inactive":
            return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
        case "suspended":
            return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
        default:
            return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
    }
}

function metadataPlan(metadata: Record<string, unknown>): string {
    const plan = metadata.plan;
    return typeof plan === "string" && plan.trim() ? plan : "—";
}

function TenantDialog({
    tenant,
    trigger,
}: {
    tenant?: TenantRecord;
    trigger: React.ReactNode;
}) {
    const createTenant = useCreateTenant();
    const updateTenant = useUpdateTenant();
    const [open, setOpen] = useState(false);
    const [name, setName] = useState(tenant?.name ?? "");
    const [slug, setSlug] = useState(tenant?.slug ?? "");
    const [status, setStatus] = useState<TenantStatus>(tenant?.status ?? "active");
    const [plan, setPlan] = useState(metadataPlan(tenant?.metadata ?? {}));
    const [websiteUrl, setWebsiteUrl] = useState("");

    const resetForm = () => {
        setName(tenant?.name ?? "");
        setSlug(tenant?.slug ?? "");
        setStatus(tenant?.status ?? "active");
        setPlan(metadataPlan(tenant?.metadata ?? {}));
        setWebsiteUrl("");
    };

    const handleOpenChange = (nextOpen: boolean) => {
        if (nextOpen) {
            resetForm();
        }
        setOpen(nextOpen);
    };

    const isEditing = Boolean(tenant);
    const isPending = createTenant.isPending || updateTenant.isPending;

    const handleSubmit = () => {
        const metadata = plan.trim() ? { plan: plan.trim() } : {};

        if (isEditing && tenant) {
            const payload: TenantUpdateRequest = {
                name: name.trim() || undefined,
                slug: slug.trim() || undefined,
                status,
                metadata,
            };
            updateTenant.mutate(
                { tenantId: tenant.id, data: payload },
                { onSuccess: () => setOpen(false) }
            );
            return;
        }

        const rawUrl = websiteUrl.trim();
        const normalizedUrl = rawUrl
            ? /^https?:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`
            : undefined;

        const payload: TenantCreateRequest = {
            name: name.trim(),
            slug: slug.trim() || undefined,
            status,
            metadata,
            website_url: normalizedUrl,
        };
        createTenant.mutate(payload, { onSuccess: () => setOpen(false) });
    };

    const error = createTenant.error?.message || updateTenant.error?.message;

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogTrigger asChild>{trigger}</DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{isEditing ? "Edit Tenant" : "Create Tenant"}</DialogTitle>
                    <DialogDescription>
                        {isEditing
                            ? "Update tenant metadata and operating status."
                            : "Create a new tenant for a client organization."}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 pt-2">
                    <div className="space-y-2">
                        <Label htmlFor="tenant-name">Tenant Name</Label>
                        <Input
                            id="tenant-name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Northwind Health"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="tenant-slug">Slug</Label>
                        <Input
                            id="tenant-slug"
                            value={slug}
                            onChange={(e) => setSlug(e.target.value)}
                            placeholder="northwind-health"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="tenant-status">Status</Label>
                        <Select value={status} onValueChange={(value) => setStatus(value as TenantStatus)}>
                            <SelectTrigger id="tenant-status">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {STATUS_OPTIONS.map((option) => (
                                    <SelectItem key={option} value={option}>
                                        {option}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="tenant-plan">Plan</Label>
                        <Input
                            id="tenant-plan"
                            value={plan === "—" ? "" : plan}
                            onChange={(e) => setPlan(e.target.value)}
                            placeholder="enterprise"
                        />
                    </div>
                    {!isEditing && (
                        <div className="space-y-2">
                            <Label htmlFor="tenant-website">Website URL</Label>
                            <Input
                                id="tenant-website"
                                type="url"
                                value={websiteUrl}
                                onChange={(e) => setWebsiteUrl(e.target.value)}
                                placeholder="https://acme.com"
                            />
                            <p className="text-xs text-muted-foreground">
                                Optional. Auto-populates the tenant knowledge base via Firecrawl.
                            </p>
                        </div>
                    )}
                    <Button
                        onClick={handleSubmit}
                        disabled={isPending || !name.trim()}
                        className="w-full"
                    >
                        {isPending ? (isEditing ? "Saving..." : "Creating...") : isEditing ? "Save Changes" : "Create Tenant"}
                    </Button>

                    {error && <p className="text-sm text-red-500">{error}</p>}
                </div>
            </DialogContent>
        </Dialog>
    );
}

export function TenantsTable({
    data,
    isLoading,
    searchValue,
    onSearchChange,
    statusValue,
    onStatusChange,
}: TenantsTableProps) {
    if (isLoading) {
        return (
            <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="h-14 animate-pulse rounded bg-muted" />
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex flex-wrap items-center gap-3">
                    <div className="relative w-full max-w-sm">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            value={searchValue}
                            onChange={(e) => onSearchChange(e.target.value)}
                            placeholder="Search tenants by name or slug..."
                            className="pl-9"
                        />
                    </div>

                    <Select value={statusValue} onValueChange={onStatusChange}>
                        <SelectTrigger className="w-[160px]">
                            <SelectValue placeholder="All statuses" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All statuses</SelectItem>
                            {STATUS_OPTIONS.map((option) => (
                                <SelectItem key={option} value={option}>
                                    {option}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <TenantDialog
                    trigger={
                        <Button size="sm">
                            <Plus className="mr-1.5 h-4 w-4" />
                            Create Tenant
                        </Button>
                    }
                />
            </div>

            {!data || data.tenants.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-muted-foreground">
                    No tenants found.
                </div>
            ) : (
                <>
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Tenant</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Readiness</TableHead>
                                    <TableHead>Plan</TableHead>
                                    <TableHead>Summary</TableHead>
                                    <TableHead>Updated</TableHead>
                                    <TableHead className="w-[180px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {data.tenants.map((tenant) => {
                                    const stage = getTenantReadinessStage(tenant);

                                    return (
                                        <TableRow key={tenant.id}>
                                            <TableCell>
                                                <div>
                                                    <p className="font-medium">{tenant.name}</p>
                                                    <p className="text-sm text-muted-foreground">{tenant.slug}</p>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusClasses(tenant.status)}`}>
                                                    {tenant.status}
                                                </span>
                                            </TableCell>
                                            <TableCell className="text-sm">
                                                <div>
                                                    <p className="font-medium">{stage.label}</p>
                                                    <p className="text-xs text-muted-foreground">{stage.detail}</p>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-sm">{metadataPlan(tenant.metadata)}</TableCell>
                                            <TableCell className="text-xs text-muted-foreground">
                                                <div>Users: {tenant.summary.user_count}</div>
                                                <div>Agents: {tenant.summary.agent_count}</div>
                                                <div>Calls: {tenant.summary.call_count}</div>
                                                <div>Numbers: {tenant.summary.phone_number_count}</div>
                                            </TableCell>
                                            <TableCell className="text-sm text-muted-foreground">
                                                {new Date(tenant.updated_at).toLocaleDateString()}
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center justify-end gap-2">
                                                    <TenantDialog
                                                        tenant={tenant}
                                                        trigger={
                                                            <Button variant="ghost" size="sm">
                                                                <Pencil className="h-4 w-4" />
                                                            </Button>
                                                        }
                                                    />
                                                    <Button asChild variant="outline" size="sm">
                                                        <Link href={`/workspace/${tenant.id}/overview`}>
                                                            Open Workspace
                                                            <ArrowRight className="h-4 w-4" />
                                                        </Link>
                                                    </Button>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </div>

                    <div className="text-sm text-muted-foreground">
                        Showing {data.tenants.length} of {data.total} tenants
                    </div>
                </>
            )}
        </div>
    );
}