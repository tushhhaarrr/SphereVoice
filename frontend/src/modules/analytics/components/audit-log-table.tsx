"use client";

import { Button } from "@/components/ui/button";
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
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChevronLeft, ChevronRight, Eye } from "lucide-react";
import type { AuditLogEntry, AuditLogListResponse, TenantRecord } from "../types";

interface AuditLogTableProps {
    data: AuditLogListResponse | undefined;
    isLoading: boolean;
    page: number;
    onPageChange: (page: number) => void;
    resourceTypeFilter: string;
    onResourceTypeChange: (value: string) => void;
    actionFilter: string;
    onActionChange: (value: string) => void;
    tenantFilter?: string;
    onTenantFilterChange?: (value: string) => void;
    tenantOptions?: TenantRecord[];
}

const ACTION_COLORS: Record<string, string> = {
    create: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    update: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    delete: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    login: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    invite: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
};

function ChangesDialog({ entry }: { entry: AuditLogEntry }) {
    if (!entry.changes) return null;

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="ghost" size="sm">
                    <Eye className="h-4 w-4" />
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>Audit Log Details</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 text-sm">
                    <div className="grid grid-cols-2 gap-2">
                        <span className="text-muted-foreground">Action:</span>
                        <span className="font-medium">{entry.action}</span>
                        <span className="text-muted-foreground">Resource:</span>
                        <span className="font-medium">{entry.resource_type}</span>
                        <span className="text-muted-foreground">Resource ID:</span>
                        <code className="text-xs">{entry.resource_id || "—"}</code>
                        <span className="text-muted-foreground">User:</span>
                        <span>{entry.user_email || entry.user_id || "System"}</span>
                        <span className="text-muted-foreground">IP:</span>
                        <span>{entry.ip_address || "—"}</span>
                        <span className="text-muted-foreground">Time:</span>
                        <span>{new Date(entry.timestamp).toLocaleString()}</span>
                    </div>
                    <div>
                        <p className="text-muted-foreground mb-1">Changes:</p>
                        <ScrollArea className="h-[200px]">
                            <pre className="rounded bg-muted p-3 text-xs overflow-x-auto">
                                {JSON.stringify(entry.changes, null, 2)}
                            </pre>
                        </ScrollArea>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}

export function AuditLogTable({
    data,
    isLoading,
    page,
    onPageChange,
    resourceTypeFilter,
    onResourceTypeChange,
    actionFilter,
    onActionChange,
    tenantFilter = "",
    onTenantFilterChange,
    tenantOptions = [],
}: AuditLogTableProps) {
    const limit = 50;
    const totalPages = data ? Math.ceil(data.total / limit) : 0;

    if (isLoading) {
        return (
            <div className="space-y-3">
                {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="h-12 animate-pulse rounded bg-muted" />
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap items-end gap-4">
                <div className="space-y-1.5">
                    <Label>Resource Type</Label>
                    <Select value={resourceTypeFilter} onValueChange={onResourceTypeChange}>
                        <SelectTrigger className="w-[160px]">
                            <SelectValue placeholder="All types" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Types</SelectItem>
                            <SelectItem value="agent">Agent</SelectItem>
                            <SelectItem value="agent_template">Template</SelectItem>
                            <SelectItem value="provider">Provider</SelectItem>
                            <SelectItem value="user">User</SelectItem>
                            <SelectItem value="call">Call</SelectItem>
                            <SelectItem value="knowledge_base">Knowledge Base</SelectItem>
                            <SelectItem value="phone_number">Phone Number</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="space-y-1.5">
                    <Label>Action</Label>
                    <Select value={actionFilter} onValueChange={onActionChange}>
                        <SelectTrigger className="w-[140px]">
                            <SelectValue placeholder="All actions" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Actions</SelectItem>
                            <SelectItem value="create">Create</SelectItem>
                            <SelectItem value="update">Update</SelectItem>
                            <SelectItem value="delete">Delete</SelectItem>
                            <SelectItem value="login">Login</SelectItem>
                            <SelectItem value="invite">Invite</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {onTenantFilterChange && (
                    <div className="space-y-1.5">
                        <Label>Tenant</Label>
                        <Select
                            value={tenantFilter || "all"}
                            onValueChange={(value) =>
                                onTenantFilterChange(value === "all" ? "" : value)
                            }
                        >
                            <SelectTrigger className="w-[220px]">
                                <SelectValue placeholder="All tenants" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All tenants</SelectItem>
                                {tenantOptions.map((tenant) => (
                                    <SelectItem key={tenant.id} value={tenant.id}>
                                        {tenant.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}
            </div>

            {!data || data.logs.length === 0 ? (
                <div className="flex h-40 items-center justify-center text-muted-foreground">
                    No audit logs found.
                </div>
            ) : (
                <>
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Time</TableHead>
                                    <TableHead>User</TableHead>
                                    <TableHead>Tenant</TableHead>
                                    <TableHead>Action</TableHead>
                                    <TableHead>Resource</TableHead>
                                    <TableHead>Resource ID</TableHead>
                                    <TableHead>IP</TableHead>
                                    <TableHead className="w-[50px]" />
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {data.logs.map((entry) => {
                                    const tenant = tenantOptions.find((item) => item.id === entry.tenant_id);
                                    return (
                                        <TableRow key={entry.id}>
                                            <TableCell className="text-sm whitespace-nowrap">
                                                {new Date(entry.timestamp).toLocaleString()}
                                            </TableCell>
                                            <TableCell className="text-sm">
                                                {entry.user_email || (
                                                    <span className="text-muted-foreground">System</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-sm">
                                                {entry.tenant_id ? tenant?.name || `${entry.tenant_id.slice(0, 8)}...` : "—"}
                                            </TableCell>
                                            <TableCell>
                                                <span
                                                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ACTION_COLORS[entry.action] ||
                                                        "bg-gray-100 text-gray-800"
                                                        }`}
                                                >
                                                    {entry.action}
                                                </span>
                                            </TableCell>
                                            <TableCell className="text-sm">
                                                {entry.resource_type.replace("_", " ")}
                                            </TableCell>
                                            <TableCell>
                                                {entry.resource_id ? (
                                                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                                                        {entry.resource_id.slice(0, 8)}...
                                                    </code>
                                                ) : (
                                                    "—"
                                                )}
                                            </TableCell>
                                            <TableCell className="text-xs text-muted-foreground">
                                                {entry.ip_address || "—"}
                                            </TableCell>
                                            <TableCell>
                                                <ChangesDialog entry={entry} />
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </div>

                    {/* Pagination */}
                    <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} ({data.total} total)
                        </span>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => onPageChange(page - 1)}
                                disabled={page <= 1}
                            >
                                <ChevronLeft className="h-4 w-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => onPageChange(page + 1)}
                                disabled={page >= totalPages}
                            >
                                <ChevronRight className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
