"use client";

/**
 * GoogleCalendarCard — displays connection status and connect/disconnect
 * controls for the Google Calendar integration.
 */

import { useState } from "react";
import {
    AlertCircle,
    Calendar,
    CheckCircle2,
    Loader2,
    RefreshCw,
    Unplug,
    Zap,
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
    useDisconnectGoogleCalendar,
    useInitiateGoogleCalendarOAuth,
    useSyncGoogleCalendar,
} from "../hooks/use-google-integrations";
import type { GoogleIntegration } from "../types";

interface GoogleCalendarCardProps {
    integration?: GoogleIntegration;
    tenantId?: string;
}

function StatusBadge({ status }: { status: string }) {
    if (status === "connected") {
        return (
            <Badge variant="default" className="gap-1 bg-green-600 hover:bg-green-600">
                <CheckCircle2 className="h-3 w-3" />
                Connected
            </Badge>
        );
    }
    if (status === "error") {
        return (
            <Badge variant="destructive" className="gap-1">
                <AlertCircle className="h-3 w-3" />
                Error
            </Badge>
        );
    }
    return (
        <Badge variant="secondary" className="gap-1">
            Not connected
        </Badge>
    );
}

export function GoogleCalendarCard({ integration, tenantId }: GoogleCalendarCardProps) {
    const [confirmDisconnect, setConfirmDisconnect] = useState(false);

    const initiate = useInitiateGoogleCalendarOAuth();
    const sync = useSyncGoogleCalendar(tenantId);
    const disconnect = useDisconnectGoogleCalendar(tenantId);

    const isConnected = !!integration && integration.status === "connected";
    const isError = !!integration && integration.status === "error";

    function handleConnect() {
        initiate.mutate({ tenantId });
    }

    function handleSync() {
        if (!integration) return;
        sync.mutate({ integrationId: integration.id });
    }

    function handleDisconnect() {
        if (!integration) return;
        disconnect.mutate({ integrationId: integration.id });
        setConfirmDisconnect(false);
    }

    return (
        <>
            <Card className="w-full">
                <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 pb-3">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-500 text-white">
                            <Calendar className="h-5 w-5" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Google Calendar</CardTitle>
                            <CardDescription className="text-xs">
                                Book appointments & check availability during calls
                            </CardDescription>
                        </div>
                    </div>

                    <StatusBadge status={integration?.status ?? "disconnected"} />
                </CardHeader>

                <CardContent className="space-y-4">
                    {/* Account details (when connected) */}
                    {integration && (isConnected || isError) && (
                        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm space-y-1">
                            {integration.account_email && (
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Account</span>
                                    <span className="font-medium">{integration.account_email}</span>
                                </div>
                            )}
                            {integration.last_synced_at && (
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Last synced</span>
                                    <span>
                                        {new Date(integration.last_synced_at).toLocaleString()}
                                    </span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Error from connect/sync/disconnect */}
                    {initiate.error && (
                        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive flex items-center gap-2">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            {initiate.error.message}
                        </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex flex-wrap items-center gap-2">
                        {!integration ? (
                            <Button
                                size="sm"
                                onClick={handleConnect}
                                disabled={initiate.isPending}
                                className="gap-1"
                            >
                                {initiate.isPending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Zap className="h-4 w-4" />
                                )}
                                Connect
                            </Button>
                        ) : (
                            <>
                                {isError && (
                                    <Button
                                        size="sm"
                                        onClick={handleConnect}
                                        disabled={initiate.isPending}
                                        className="gap-1"
                                    >
                                        {initiate.isPending ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Zap className="h-4 w-4" />
                                        )}
                                        Reconnect
                                    </Button>
                                )}
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={handleSync}
                                    disabled={sync.isPending}
                                    className="gap-1"
                                >
                                    {sync.isPending ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <RefreshCw className="h-4 w-4" />
                                    )}
                                    Sync
                                </Button>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setConfirmDisconnect(true)}
                                    disabled={disconnect.isPending}
                                    className="gap-1 text-destructive hover:text-destructive"
                                >
                                    <Unplug className="h-4 w-4" />
                                    Disconnect
                                </Button>
                            </>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Disconnect confirmation */}
            <AlertDialog open={confirmDisconnect} onOpenChange={setConfirmDisconnect}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Disconnect Google Calendar?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will revoke the OAuth connection. Agents using calendar tools
                            will no longer be able to create events until reconnected.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDisconnect}>
                            Disconnect
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
