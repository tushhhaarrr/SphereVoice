"use client";

/**
 * Agent list with TanStack Table.
 *
 * Sortable columns, status badges, and action buttons.
 */

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
    Loader2,
    PhoneIncoming,
    PhoneOutgoing,
    Plus,
    Rocket,
    Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAgents, useDeleteAgent, usePublishAgent } from "../hooks/use-agents";
import { RoleGuard } from "@/modules/auth";
import { CreateAgentDialog } from "./create-agent-dialog";
import type { Agent, AgentStatus, AgentType, CallDirection } from "../types";

const STATUS_STYLES: Record<AgentStatus, string> = {
    draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    published: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    archived: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const TYPE_LABELS: Record<AgentType, string> = {
    conversation_flow: "Flow",
    single_prompt: "Prompt",
};

const columnHelper = createColumnHelper<Agent>();

interface AgentListProps {
    tenantId?: string;
    tenantName?: string;
}

export function AgentList({ tenantId, tenantName }: AgentListProps = {}) {
    const [sorting, setSorting] = useState<SortingState>([]);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const { data, isLoading, error } = useAgents({ tenantId });
    const deleteMutation = useDeleteAgent();
    const publishMutation = usePublishAgent();
    const workspaceMode = Boolean(tenantId);

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
                    tenantId ? (
                        <Link
                            href={`/workspace/${tenantId}/agents/${info.row.original.id}`}
                            className="font-medium hover:underline"
                        >
                            {info.getValue()}
                        </Link>
                    ) : (
                        <span className="font-medium">{info.getValue()}</span>
                    )
                ),
            }),
            columnHelper.accessor("type", {
                header: "Type",
                cell: (info) => (
                    <Badge variant="outline">
                        {TYPE_LABELS[info.getValue() as AgentType] || info.getValue()}
                    </Badge>
                ),
            }),
            columnHelper.accessor("call_direction", {
                header: "Direction",
                cell: (info) => {
                    const dir = (info.getValue() as CallDirection) || "inbound";
                    return (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                            {dir === "outbound" ? (
                                <><PhoneOutgoing className="h-3 w-3" /> Outbound</>
                            ) : (
                                <><PhoneIncoming className="h-3 w-3" /> Inbound</>
                            )}
                        </span>
                    );
                },
            }),
            columnHelper.accessor("status", {
                header: "Status",
                cell: (info) => {
                    const status = info.getValue() as AgentStatus;
                    return (
                        <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] || ""}`}
                        >
                            {status}
                        </span>
                    );
                },
            }),
            columnHelper.accessor("version", {
                header: "Version",
                cell: (info) => <span className="text-muted-foreground">v{info.getValue()}</span>,
            }),
            columnHelper.accessor("language", {
                header: "Language",
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
                    const agent = row.original;
                    return (
                        <div className="flex justify-end gap-1">
                            <RoleGuard roles={["admin", "developer"]}>
                                {agent.status === "draft" && (
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => publishMutation.mutate(agent.id)}
                                        disabled={publishMutation.isPending}
                                        aria-label="Publish agent"
                                    >
                                        <Rocket className="h-4 w-4" />
                                    </Button>
                                )}
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => {
                                        if (confirm(`Delete agent "${agent.name}"?`)) {
                                            deleteMutation.mutate(agent.id);
                                        }
                                    }}
                                    aria-label="Delete agent"
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
        [deleteMutation, publishMutation, tenantId]
    );

    const table = useReactTable({
        data: data?.agents ?? [],
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
        const isAuthError = error.message?.toLowerCase().includes("session expired") ||
            error.message?.toLowerCase().includes("unauthorized");
        return (
            <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {isAuthError
                    ? "Session expired. Please refresh the page or sign in again."
                    : "Failed to load agents. Make sure the backend is running."}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Agents</h1>
                    <p className="text-sm text-muted-foreground">
                        {workspaceMode
                            ? `Create and manage agents for ${tenantName ?? "this workspace"}`
                            : "Create and manage voice AI agents"}
                    </p>
                    {workspaceMode ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span className="rounded-full border px-3 py-1">Tenant workspace</span>
                            <span className="rounded-full border px-3 py-1">Only this tenant&apos;s agents are shown</span>
                        </div>
                    ) : null}
                </div>
                <RoleGuard roles={["admin", "developer"]}>
                    <Button onClick={() => setCreateDialogOpen(true)} disabled={!workspaceMode}>
                        <Plus className="mr-2 h-4 w-4" />
                        New Agent
                    </Button>
                </RoleGuard>
            </div>

            {workspaceMode && tenantId ? (
                <CreateAgentDialog
                    open={createDialogOpen}
                    onOpenChange={setCreateDialogOpen}
                    tenantId={tenantId}
                    tenantName={tenantName}
                />
            ) : null}

            {/* TanStack Table */}
            {(data?.agents?.length ?? 0) === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
                    <p className="text-sm text-muted-foreground">
                        {workspaceMode
                            ? `No agents created yet for ${tenantName ?? "this workspace"}.`
                            : "No agents created yet."}
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
                        Showing {data.agents.length} of {data.total} agents
                    </span>
                    <span>Page {data.page}</span>
                </div>
            )}
        </div>
    );
}
