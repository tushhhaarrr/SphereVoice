"use client";

/**
 * CrmSyncStatusPanel — shows sync status badge, record counts,
 * last synced time, and a "Sync Now" button.
 */

import {
    Database,
    Loader2,
    RefreshCw,
    Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

import { useSyncStatus, useTriggerSync } from "../hooks/use-crm-data";

function formatTimeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

export function CrmSyncStatusPanel({ tenantId }: { tenantId?: string }) {
    const { data: status, isLoading } = useSyncStatus(tenantId);
    const triggerSync = useTriggerSync(tenantId);

    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (!status) return null;

    const lastSynced = status.last_synced_at
        ? formatTimeAgo(status.last_synced_at)
        : "Never";

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Database className="h-4 w-4 text-muted-foreground" />
                        <CardTitle className="text-base">Local CRM Cache</CardTitle>
                    </div>
                    {status.sync_in_progress ? (
                        <Badge variant="secondary" className="gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Syncing…
                        </Badge>
                    ) : (
                        <Badge variant="outline" className="text-xs">
                            Last synced {lastSynced}
                        </Badge>
                    )}
                </div>
                <CardDescription>
                    Contacts and leads are cached locally for instant caller enrichment.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="flex items-center justify-between">
                    <div className="flex gap-6">
                        <div className="flex items-center gap-1.5">
                            <Users className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-sm font-medium">
                                {status.contacts_cached}
                            </span>
                            <span className="text-xs text-muted-foreground">contacts</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <Users className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-sm font-medium">
                                {status.leads_cached}
                            </span>
                            <span className="text-xs text-muted-foreground">leads</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="text-sm font-medium text-primary">
                                {status.total_cached}
                            </span>
                            <span className="text-xs text-muted-foreground">total</span>
                        </div>
                    </div>
                    <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5"
                        onClick={() => triggerSync.mutate()}
                        disabled={status.sync_in_progress || triggerSync.isPending}
                    >
                        {triggerSync.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        Sync Now
                    </Button>
                </div>
                {triggerSync.isSuccess && triggerSync.data?.status === "triggered" && (
                    <p className="mt-2 text-xs text-muted-foreground">
                        Sync started — records will update in the background.
                    </p>
                )}
                {triggerSync.isSuccess && triggerSync.data?.status === "already_running" && (
                    <p className="mt-2 text-xs text-amber-600">
                        A sync is already in progress.
                    </p>
                )}
            </CardContent>
        </Card>
    );
}
