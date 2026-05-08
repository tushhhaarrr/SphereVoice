"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
    createColumnHelper,
    flexRender,
    getCoreRowModel,
    getSortedRowModel,
    useReactTable,
    type SortingState,
} from "@tanstack/react-table";
import {
    ArrowUpDown,
    Copy,
    Loader2,
    Plus,
    Trash2,
    Eye,
    Clock,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCampaigns, useDeleteCampaign, useCloneCampaign } from "../hooks/use-campaigns";
import { RoleGuard } from "@/modules/auth";
import type { CampaignListItem, CampaignStatus } from "../types";
import {
    getCampaignStatusColor,
    getCampaignStatusLabel,
    formatProgress,
    getProgressPercent,
} from "../lib/campaign-utils";

const columnHelper = createColumnHelper<CampaignListItem>();

export interface CampaignListProps {
    tenantId: string;
}

export function CampaignList({ tenantId }: CampaignListProps) {
    const [sorting, setSorting] = useState<SortingState>([]);
    const { data, isLoading, error } = useCampaigns({ tenant_id: tenantId });
    const deleteMutation = useDeleteCampaign();
    const cloneMutation = useCloneCampaign();

    const columns = useMemo(
        () => [
            columnHelper.accessor("name", {
                header: ({ column }) => (
                    <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3"
                        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    >
                        Name
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                    </Button>
                ),
                cell: (info) => (
                    <Link
                        href={`/workspace/${tenantId}/campaigns/${info.row.original.id}`}
                        className="font-medium hover:underline"
                    >
                        {info.getValue()}
                    </Link>
                ),
            }),
            columnHelper.accessor("status", {
                header: "Status",
                cell: (info) => {
                    const status = info.getValue() as CampaignStatus;
                    const colors = getCampaignStatusColor(status);
                    const scheduledAt = info.row.original.scheduled_at;
                    return (
                        <div className="flex flex-col gap-1">
                            <span
                                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}
                            >
                                <span className={`h-1.5 w-1.5 rounded-full ${colors.dot}`} />
                                {getCampaignStatusLabel(status)}
                            </span>
                            {scheduledAt && (status === "draft" || status === "scheduled") && (
                                <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                                    <Clock className="h-3 w-3" />
                                    {new Date(scheduledAt).toLocaleString(undefined, {
                                        month: "short",
                                        day: "numeric",
                                        hour: "2-digit",
                                        minute: "2-digit",
                                    })}
                                </span>
                            )}
                        </div>
                    );
                },
            }),
            columnHelper.accessor("total_contacts", {
                header: "Contacts",
                cell: (info) => info.getValue(),
            }),
            columnHelper.accessor((row) => row, {
                id: "progress",
                header: "Progress",
                cell: (info) => {
                    const { completed_calls, total_contacts } = info.getValue();
                    return (
                        <div className="flex items-center gap-2">
                            <div className="h-2 w-16 rounded-full bg-muted">
                                <div
                                    className="h-full rounded-full bg-primary"
                                    style={{
                                        width: `${getProgressPercent(completed_calls, total_contacts)}%`,
                                    }}
                                />
                            </div>
                            <span className="text-xs text-muted-foreground">
                                {formatProgress(completed_calls, total_contacts)}
                            </span>
                        </div>
                    );
                },
            }),
            columnHelper.accessor("created_at", {
                header: ({ column }) => (
                    <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3"
                        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    >
                        Created
                        <ArrowUpDown className="ml-2 h-3 w-3" />
                    </Button>
                ),
                cell: (info) => new Date(info.getValue()).toLocaleDateString(),
            }),
            columnHelper.display({
                id: "actions",
                header: () => <span className="sr-only">Actions</span>,
                cell: ({ row }) => {
                    const campaign = row.original;
                    return (
                        <div className="flex justify-end gap-1">
                            <Button
                                variant="ghost"
                                size="icon"
                                asChild
                                aria-label="View campaign"
                            >
                                <Link href={`/workspace/${tenantId}/campaigns/${campaign.id}`}>
                                    <Eye className="h-4 w-4" />
                                </Link>
                            </Button>
                            <RoleGuard roles={["admin", "developer"]}>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => cloneMutation.mutate({ campaignId: campaign.id, tenantId })}
                                    aria-label="Clone campaign"
                                    disabled={cloneMutation.isPending}
                                >
                                    <Copy className="h-4 w-4" />
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => {
                                        if (confirm(`Delete campaign "${campaign.name}"?`)) {
                                            deleteMutation.mutate({ id: campaign.id, tenantId });
                                        }
                                    }}
                                    aria-label="Delete campaign"
                                    className="text-destructive hover:text-destructive"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </RoleGuard>
                        </div>
                    );
                },
            }),
        ],
        [deleteMutation, cloneMutation, tenantId]
    );

    const table = useReactTable({
        data: data?.campaigns ?? [],
        columns,
        state: { sorting },
        onSortingChange: setSorting,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
    });

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        const isAuthError =
            error.message?.toLowerCase().includes("session expired") ||
            error.message?.toLowerCase().includes("unauthorized");
        return (
            <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {isAuthError
                    ? "Session expired. Please refresh the page or sign in again."
                    : "Failed to load campaigns. Make sure the backend is running."}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Campaigns</h1>
                    <p className="text-sm text-muted-foreground">
                        Create and manage outbound campaigns
                    </p>
                </div>
                <RoleGuard roles={["admin", "developer"]}>
                    <Button asChild>
                        <Link href={`/workspace/${tenantId}/campaigns/new`}>
                            <Plus className="mr-2 h-4 w-4" />
                            New Campaign
                        </Link>
                    </Button>
                </RoleGuard>
            </div>

            {/* TanStack Table */}
            {(data?.campaigns?.length ?? 0) === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
                    <p className="text-sm text-muted-foreground">
                        No campaigns created yet.
                    </p>
                </div>
            ) : (
                <div className="rounded-md border">
                    <table className="w-full text-sm">
                        <thead>
                            {table.getHeaderGroups().map((headerGroup) => (
                                <tr key={headerGroup.id} className="border-b bg-muted/50">
                                    {headerGroup.headers.map((header) => (
                                        <th
                                            key={header.id}
                                            className="px-4 py-3 text-left font-medium"
                                        >
                                            {header.isPlaceholder
                                                ? null
                                                : flexRender(
                                                    header.column.columnDef.header,
                                                    header.getContext()
                                                )}
                                        </th>
                                    ))}
                                </tr>
                            ))}
                        </thead>
                        <tbody>
                            {table.getRowModel().rows.map((row) => (
                                <tr
                                    key={row.id}
                                    className="border-b last:border-0 hover:bg-muted/30"
                                >
                                    {row.getVisibleCells().map((cell) => (
                                        <td key={cell.id} className="px-4 py-3">
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Pagination info */}
            {data && data.total > 0 && (
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>
                        Showing {data?.campaigns?.length ?? 0} of {data.total} campaigns
                    </span>
                </div>
            )}
        </div>
    );
}
