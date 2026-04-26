"use client";

/**
 * Version History Sidebar — List published versions with timestamps and rollback.
 *
 * Displays all immutable snapshots of an agent's config.
 * Allows rolling back to a previous version.
 */

import { Loader2, RotateCcw, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAgentVersions, useRollbackAgent } from "../hooks/use-agent-versions";
import { formatDate } from "@/lib/utils";

interface VersionHistorySidebarProps {
  agentId: string;
  currentVersion: number;
  onClose?: () => void;
}

export function VersionHistorySidebar({
  agentId,
  currentVersion,
  onClose,
}: VersionHistorySidebarProps) {
  const { data: versionsData, isLoading, error } = useAgentVersions(agentId);
  const rollbackMutation = useRollbackAgent();

  const handleRollback = (version: number) => {
    if (
      confirm(
        `Roll back to version ${version}? This will replace the current draft with the config from v${version}.`
      )
    ) {
      rollbackMutation.mutate({ agentId, version });
    }
  };

  return (
    <div className="flex h-full w-[280px] flex-col border-l bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold">Version History</h3>
          <p className="text-xs text-muted-foreground">
            Published snapshots of this agent
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose} className="h-6 w-6 p-0">
            <span className="sr-only">Close</span>
            ×
          </Button>
        )}
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              Failed to load versions.
            </div>
          )}

          {versionsData?.versions.length === 0 && !isLoading && (
            <div className="flex flex-col items-center py-8 text-center">
              <Clock className="mb-2 h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No versions published yet.</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Publish to create the first version.
              </p>
            </div>
          )}

          {versionsData?.versions.map((version) => (
            <div
              key={version.id}
              className="rounded-lg border p-3 space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={version.version === currentVersion ? "default" : "outline"}
                  >
                    v{version.version}
                  </Badge>
                  {version.version === currentVersion && (
                    <span className="text-[10px] font-medium text-green-600">
                      CURRENT
                    </span>
                  )}
                </div>
              </div>

              <div className="text-xs text-muted-foreground">
                <p>Published {formatDate(version.published_at)}</p>
              </div>

              {version.version !== currentVersion && (
                <>
                  <Separator />
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => handleRollback(version.version)}
                    disabled={rollbackMutation.isPending}
                  >
                    {rollbackMutation.isPending ? (
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    ) : (
                      <RotateCcw className="mr-1 h-3 w-3" />
                    )}
                    Rollback to v{version.version}
                  </Button>
                </>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
