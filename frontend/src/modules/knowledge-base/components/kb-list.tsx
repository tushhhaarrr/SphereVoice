"use client";

/**
 * Knowledge Base list component.
 *
 * Displays all knowledge bases in a table with document counts,
 * sharing scope badges, and action buttons (view, delete).
 */

import { useState } from "react";
import { Plus, Trash2, FileText, Search, Library, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
    useKnowledgeBases,
    useDeleteKnowledgeBase,
} from "../hooks/use-knowledge-base";
import type { KnowledgeBase, KBStatus, SharingScope } from "../types";
import { CreateKBDialog } from "./create-kb-dialog";
import { KBDetailPanel } from "./kb-detail-panel";
import { RoleGuard } from "@/modules/auth";

const SCOPE_COLORS: Record<SharingScope, string> = {
    private: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
    tenant:
        "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    global:
        "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

const STATUS_BADGE: Record<KBStatus, { label: string; cls: string; spin?: boolean }> = {
    ready:      { label: "Ready",      cls: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
    pending:    { label: "Pending",    cls: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200", spin: true },
    processing: { label: "Processing", cls: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200", spin: true },
    failed:     { label: "Failed",     cls: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
};

function KBStatusBadge({ status }: { status: KBStatus }) {
    const cfg = STATUS_BADGE[status] ?? STATUS_BADGE.ready;
    return (
        <Badge variant="outline" className={`flex items-center gap-1 ${cfg.cls}`}>
            {cfg.spin && <Loader2 className="h-3 w-3 animate-spin" />}
            {cfg.label}
        </Badge>
    );
}

interface KnowledgeBaseListProps {
    tenantId?: string;
    tenantName?: string;
}

export function KnowledgeBaseList({ tenantId, tenantName }: KnowledgeBaseListProps = {}) {
    const [searchQuery, setSearchQuery] = useState("");
    const [page, setPage] = useState(1);
    const [showCreate, setShowCreate] = useState(false);
    const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
    const [deleteKbId, setDeleteKbId] = useState<string | null>(null);
    const workspaceMode = Boolean(tenantId);

    const { data, isLoading, error } = useKnowledgeBases({
        page,
        pageSize: 20,
        search: searchQuery || undefined,
        tenantId,
        // Poll every 4 s while any KB is still processing/pending
        refetchInterval: (query) => {
            const items = (query.state.data as { items?: KnowledgeBase[] } | undefined)?.items ?? [];
            const hasInFlight = items.some(
                (kb) => kb.status === "pending" || kb.status === "processing"
            );
            return hasInFlight ? 4000 : false;
        },
    });
    const deleteMutation = useDeleteKnowledgeBase();

    const handleDelete = async () => {
        if (!deleteKbId) return;
        try {
            await deleteMutation.mutateAsync(deleteKbId);
        } catch {
            // Error handled by mutation
        }
        setDeleteKbId(null);
    };

    if (error) {
        return (
            <div className="flex items-center justify-center p-8 text-destructive">
                Failed to load knowledge bases.
            </div>
        );
    }

    return (
        <div className="scroll-mt-40 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Knowledge Base</h2>
                    <p className="text-muted-foreground">
                        {workspaceMode
                            ? `Manage tenant and shared knowledge bases for ${tenantName ?? "this workspace"}.`
                            : "Manage document collections for your AI agents."}
                    </p>
                    {workspaceMode ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span className="rounded-full border px-3 py-1">Tenant workspace</span>
                            <span className="rounded-full border px-3 py-1">Global KBs remain visible</span>
                        </div>
                    ) : null}
                </div>
                <RoleGuard roles={["admin", "developer"]}>
                    <Button className="scroll-mt-40" onClick={() => setShowCreate(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        New Knowledge Base
                    </Button>
                </RoleGuard>
            </div>

            {/* Search */}
            <div className="flex items-center gap-2">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        placeholder="Search knowledge bases..."
                        value={searchQuery}
                        onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setPage(1);
                        }}
                        className="pl-9"
                    />
                </div>
            </div>

            {/* Table */}
            {isLoading ? (
                <div className="flex items-center justify-center p-12 text-muted-foreground">
                    Loading...
                </div>
            ) : !data || data.items.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
                    <Library className="h-10 w-10 text-muted-foreground mb-3" />
                    <h3 className="text-lg font-medium">No knowledge bases yet</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                        Create your first knowledge base to get started.
                    </p>
                    <RoleGuard roles={["admin", "developer"]}>
                        <Button
                            variant="outline"
                            className="mt-4 scroll-mt-40"
                            onClick={() => setShowCreate(true)}
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            Create Knowledge Base
                        </Button>
                    </RoleGuard>
                </div>
            ) : (
                <>
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Documents</TableHead>
                                    <TableHead>Scope</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="w-[100px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {data.items.map((kb: KnowledgeBase) => (
                                    <TableRow
                                        key={kb.id}
                                        className="cursor-pointer hover:bg-muted/50"
                                        onClick={() => setSelectedKbId(kb.id)}
                                    >
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <FileText className="h-4 w-4 text-muted-foreground" />
                                                <div>
                                                    <div className="font-medium">{kb.name}</div>
                                                    {kb.description && (
                                                        <div className="text-xs text-muted-foreground line-clamp-1">
                                                            {kb.description}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <KBStatusBadge status={kb.status ?? "ready"} />
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary">
                                                {kb.document_count} docs
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className={SCOPE_COLORS[kb.sharing_scope]}
                                            >
                                                {kb.sharing_scope}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {new Date(kb.created_at).toLocaleDateString()}
                                        </TableCell>
                                        <TableCell>
                                            <RoleGuard roles={["admin", "developer"]}>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setDeleteKbId(kb.id);
                                                    }}
                                                >
                                                    <Trash2 className="h-4 w-4 text-destructive" />
                                                </Button>
                                            </RoleGuard>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>

                    {/* Pagination */}
                    {data.total > 20 && (
                        <div className="flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">
                                Page {page} of {Math.ceil(data.total / 20)}
                            </p>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page === 1}
                                    onClick={() => setPage(page - 1)}
                                >
                                    Previous
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page * 20 >= data.total}
                                    onClick={() => setPage(page + 1)}
                                >
                                    Next
                                </Button>
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* Create Dialog */}
            <CreateKBDialog
                open={showCreate}
                onOpenChange={setShowCreate}
                tenantId={tenantId}
                tenantName={tenantName}
            />

            {/* Detail Panel */}
            {selectedKbId && (
                <KBDetailPanel
                    kbId={selectedKbId}
                    open={!!selectedKbId}
                    onOpenChange={(open) => {
                        if (!open) setSelectedKbId(null);
                    }}
                />
            )}

            {/* Delete Confirmation */}
            <AlertDialog
                open={!!deleteKbId}
                onOpenChange={(open) => {
                    if (!open) setDeleteKbId(null);
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Knowledge Base?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will permanently delete this knowledge base and all its
                            documents and embeddings. This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDelete}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleteMutation.isPending ? "Deleting..." : "Delete"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
