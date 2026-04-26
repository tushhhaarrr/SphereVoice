"use client";

import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
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
  useDisconnectIntegration,
  useInitiateHubSpotOAuth,
  useSyncIntegration,
} from "../hooks/use-integrations";
import type { CrmIntegration } from "../types";

interface HubSpotCrmCardProps {
  integration?: CrmIntegration;
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

export function HubSpotCrmCard({ integration, tenantId }: HubSpotCrmCardProps) {
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const initiate = useInitiateHubSpotOAuth();
  const sync = useSyncIntegration(tenantId);
  const disconnect = useDisconnectIntegration(tenantId);

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
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[#ff7a59] text-white font-bold text-sm select-none">
              H
            </div>
            <div>
              <CardTitle className="text-base">HubSpot CRM</CardTitle>
              <CardDescription className="text-xs">
                Sync contacts, deals & tickets with your voice agents
              </CardDescription>
            </div>
          </div>

          <StatusBadge status={integration?.status ?? "disconnected"} />
        </CardHeader>

        <CardContent className="space-y-4">
          {integration && (isConnected || isError) && (
            <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm space-y-1">
              {integration.org_name && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Organisation</span>
                  <span className="font-medium">{integration.org_name}</span>
                </div>
              )}
              {integration.org_id && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Org ID</span>
                  <span className="font-mono text-xs">{integration.org_id}</span>
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

                {isConnected && (
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
                )}

                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1 text-destructive hover:text-destructive"
                  onClick={() => setConfirmDisconnect(true)}
                  disabled={disconnect.isPending}
                >
                  {disconnect.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Unplug className="h-4 w-4" />
                  )}
                  Disconnect
                </Button>
              </>
            )}

            <Button size="sm" variant="ghost" asChild className="gap-1 ml-auto">
              <a
                href="https://www.hubspot.com/"
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-3 w-3" />
                Learn more
              </a>
            </Button>
          </div>

          {sync.isSuccess && (
            <p className="text-xs text-green-600 dark:text-green-400">
              ✓ {sync.data.message}
            </p>
          )}
          {sync.isError && (
            <p className="text-xs text-destructive">{sync.error.message}</p>
          )}
          {initiate.isError && (
            <p className="text-xs text-destructive">{initiate.error.message}</p>
          )}
          {disconnect.isError && (
            <p className="text-xs text-destructive">{disconnect.error.message}</p>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={confirmDisconnect} onOpenChange={setConfirmDisconnect}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect HubSpot CRM?</AlertDialogTitle>
            <AlertDialogDescription>
              This will revoke the OAuth tokens and remove the integration. Your
              HubSpot CRM data will not be deleted. You can reconnect at any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDisconnect}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Disconnect
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
