"use client";

/**
 * Webhook Delivery Log — table of delivery attempts with status, replay.
 */

import { RefreshCw, RotateCcw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
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
    useReplayDelivery,
    useWebhookDeliveries,
    type WebhookDelivery,
} from "@/modules/webhooks";

// ── Helpers ─────────────────────────────────────────────────

function statusBadge(status: WebhookDelivery["status"]) {
    const config = {
        pending: "bg-yellow-100 text-yellow-700",
        success: "bg-green-100 text-green-700",
        failed: "bg-red-100 text-red-700",
    } as const;
    return <Badge className={config[status]}>{status}</Badge>;
}

function formatDate(iso: string): string {
    try {
        return new Date(iso).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
    } catch {
        return iso;
    }
}

// ── Component ───────────────────────────────────────────────

interface WebhookDeliveryLogProps {
    webhookId?: string;
}

export function WebhookDeliveryLog({ webhookId }: WebhookDeliveryLogProps) {
    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [page, setPage] = useState(1);

    const filterStatus = statusFilter === "all" ? undefined : statusFilter;
    const { data, isLoading, refetch } = useWebhookDeliveries({
        webhookId,
        status: filterStatus,
        page,
        limit: 20,
    });
    const replay = useReplayDelivery();

    const deliveries = data?.deliveries ?? [];
    const total = data?.total ?? 0;
    const hasNextPage = page * 20 < total;

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-base">Delivery Log</CardTitle>
                        <CardDescription>
                            {total} delivery attempt{total !== 1 ? "s" : ""}
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="w-[130px]">
                                <SelectValue placeholder="Filter status" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All</SelectItem>
                                <SelectItem value="pending">Pending</SelectItem>
                                <SelectItem value="success">Success</SelectItem>
                                <SelectItem value="failed">Failed</SelectItem>
                            </SelectContent>
                        </Select>
                        <Button
                            variant="outline"
                            size="icon"
                            onClick={() => void refetch()}
                        >
                            <RefreshCw className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                ) : deliveries.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                        No deliveries found
                    </p>
                ) : (
                    <>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Event</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>HTTP</TableHead>
                                    <TableHead>Attempts</TableHead>
                                    <TableHead>Date</TableHead>
                                    <TableHead className="w-[80px]" />
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {deliveries.map((d) => (
                                    <TableRow key={d.id}>
                                        <TableCell className="font-mono text-xs">
                                            {d.event_type}
                                        </TableCell>
                                        <TableCell>{statusBadge(d.status)}</TableCell>
                                        <TableCell className="text-xs">
                                            {d.response_status_code ?? "—"}
                                        </TableCell>
                                        <TableCell className="text-xs">{d.attempts}</TableCell>
                                        <TableCell className="text-xs">
                                            {formatDate(d.created_at)}
                                        </TableCell>
                                        <TableCell>
                                            {d.status === "failed" && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    disabled={replay.isPending}
                                                    onClick={() => replay.mutate(d.id)}
                                                >
                                                    <RotateCcw className="mr-1 h-3.5 w-3.5" />
                                                    Retry
                                                </Button>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>

                        {/* Pagination */}
                        <div className="mt-4 flex items-center justify-between">
                            <p className="text-xs text-muted-foreground">
                                Page {page} of {Math.ceil(total / 20)}
                            </p>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page <= 1}
                                    onClick={() => setPage((p) => p - 1)}
                                >
                                    Previous
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={!hasNextPage}
                                    onClick={() => setPage((p) => p + 1)}
                                >
                                    Next
                                </Button>
                            </div>
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
