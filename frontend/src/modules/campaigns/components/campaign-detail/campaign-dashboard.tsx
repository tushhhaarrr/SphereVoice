"use client";

import { useState } from "react";
import { ArrowLeft, BarChart3, Copy, Database, Download, Loader2, Pause, Play, RefreshCw, Square, Upload, Users, XCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useCampaign,
  useCampaignStats,
  useStartCampaign,
  usePauseCampaign,
  useResumeCampaign,
  useCancelCampaign,
  useExportResults,
  useLoadContactsFromCrm,
  useCloneCampaign,
  useRetryAllFailed,
} from "../../hooks/use-campaigns";
import { useCampaignStream } from "../../hooks/use-campaign-stream";
import {
  getCampaignStatusColor,
  getCampaignStatusLabel,
  getProgressPercent,
  formatProgress,
  formatDateTime,
  downloadBlob,
} from "../../lib/campaign-utils";
import { CampaignStatsCards } from "./campaign-stats-cards";
import { CampaignContactsTable } from "./campaign-contacts-table";
import { CampaignAnalytics } from "./campaign-analytics";
import { ContactPreview } from "./contact-preview";
import { DryRunDialog } from "./dry-run-dialog";
import { StepCsvUpload } from "../campaign-builder/step-csv-upload";

type DashboardTab = "overview" | "contacts" | "analytics";

interface CampaignDashboardProps {
  campaignId: string;
  tenantId: string;
}

export function CampaignDashboard({ campaignId, tenantId }: CampaignDashboardProps) {
  const router = useRouter();
  const campaign = useCampaign(campaignId, tenantId);
  const stats = useCampaignStats(campaignId, tenantId);

  const startCampaign = useStartCampaign();
  const pauseCampaign = usePauseCampaign();
  const resumeCampaign = useResumeCampaign();
  const cancelCampaign = useCancelCampaign();
  const exportResults = useExportResults();
  const cloneCampaign = useCloneCampaign();
  const retryAllFailed = useRetryAllFailed(campaignId, tenantId);

  const loadFromCrm = useLoadContactsFromCrm(campaignId, tenantId);
  const [crmLoadResult, setCrmLoadResult] = useState<string | null>(null);
  const [showCsvUpload, setShowCsvUpload] = useState(false);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

  // Live streaming — auto-refresh stats while campaign is active
  useCampaignStream(campaignId, campaign.data?.status);

  const status = campaign.data?.status;
  const statusColors = status ? getCampaignStatusColor(status) : null;
  const progressPercent = stats.data ? getProgressPercent(stats.data.completed_calls, stats.data.total_contacts) : 0;

  const isActionPending =
    startCampaign.isPending ||
    pauseCampaign.isPending ||
    resumeCampaign.isPending ||
    cancelCampaign.isPending ||
    cloneCampaign.isPending;

  const handleExport = () => {
    exportResults.mutate({ campaignId, tenantId }, {
      onSuccess: (blob) => {
        downloadBlob(blob, `campaign-${campaignId}-results.csv`);
      },
    });
  };

  const handleLoadFromCrm = () => {
    setCrmLoadResult(null);
    loadFromCrm.mutate(undefined, {
      onSuccess: (data: { loaded: number }) => {
        setCrmLoadResult(`Loaded ${data.loaded} contacts from CRM`);
      },
    });
  };

  if (campaign.isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        Loading campaign…
      </div>
    );
  }

  if (campaign.error || !campaign.data) {
    return (
      <div className="flex items-center justify-center py-20 text-destructive">
        Failed to load campaign.
      </div>
    );
  }

  const c = campaign.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href={`/workspace/${tenantId}/campaigns`}>
                <ArrowLeft className="mr-1 h-4 w-4" />
                Campaigns
              </Link>
            </Button>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">{c.name}</h2>
          {c.description && (
            <p className="text-sm text-muted-foreground">{c.description}</p>
          )}
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span>Created {formatDateTime(c.created_at)}</span>
            {statusColors && (
              <Badge variant="outline" className={`${statusColors.bg} ${statusColors.text} border-0`}>
                <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${statusColors.dot}`} />
                {getCampaignStatusLabel(c.status)}
              </Badge>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
          {status === "ready" && (
            <Button
              size="sm"
              disabled={isActionPending}
              onClick={() => startCampaign.mutate({ id: campaignId, tenantId })}
            >
              <Play className="mr-1 h-4 w-4" />
              Start
            </Button>
          )}
          {status === "running" && (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={isActionPending}
                onClick={() => pauseCampaign.mutate({ id: campaignId, tenantId })}
              >
                <Pause className="mr-1 h-4 w-4" />
                Pause
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={isActionPending}
                onClick={() => cancelCampaign.mutate({ id: campaignId, tenantId })}
              >
                <XCircle className="mr-1 h-4 w-4" />
                Cancel
              </Button>
            </>
          )}
          {status === "paused" && (
            <>
              <Button
                size="sm"
                disabled={isActionPending}
                onClick={() => resumeCampaign.mutate({ id: campaignId, tenantId })}
              >
                <Play className="mr-1 h-4 w-4" />
                Resume
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={isActionPending}
                onClick={() => cancelCampaign.mutate({ id: campaignId, tenantId })}
              >
                <Square className="mr-1 h-4 w-4" />
                Cancel
              </Button>
            </>
          )}

          {/* Export — always available when there are contacts */}
          {(stats.data?.total_contacts ?? 0) > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={exportResults.isPending}
              onClick={handleExport}
            >
              <Download className="mr-1 h-4 w-4" />
              {exportResults.isPending ? "Exporting…" : "Export CSV"}
            </Button>
          )}

          {/* Clone — always available */}
          <Button
            variant="outline"
            size="sm"
            disabled={cloneCampaign.isPending}
            onClick={() => {
              cloneCampaign.mutate({ campaignId, tenantId }, {
                onSuccess: (data) => {
                  router.push(`/workspace/${tenantId}/campaigns/${data.id}`);
                },
              });
            }}
          >
            {cloneCampaign.isPending ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Copy className="mr-1 h-4 w-4" />
            )}
            Clone
          </Button>

          {/* Test Run — simulate calls without dialing */}
          <DryRunDialog
            campaignId={campaignId}
            tenantId={tenantId}
            hasContacts={(stats.data?.total_contacts ?? 0) > 0}
            disabled={isActionPending}
          />

          {/* Retry All Failed — when there are failed contacts */}
          {(stats.data?.failed_calls ?? 0) > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={retryAllFailed.isPending}
              onClick={() => retryAllFailed.mutate()}
            >
              {retryAllFailed.isPending ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-1 h-4 w-4" />
              )}
              Retry All Failed
            </Button>
          )}

          {/* Load from CRM — available for draft/ready campaigns with CRM source */}
          {(status === "draft" || status === "ready") &&
            (c.source_type === "crm" || c.source_type === "zoho_crm") && (
              <>
                <ContactPreview campaignId={campaignId} tenantId={tenantId} />
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loadFromCrm.isPending}
                  onClick={handleLoadFromCrm}
                >
                  {loadFromCrm.isPending ? (
                    <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                  ) : (
                    <Database className="mr-1 h-4 w-4" />
                  )}
                  {loadFromCrm.isPending ? "Loading…" : "Load from CRM"}
                </Button>
              </>
            )}

          {/* Upload CSV — available for draft campaigns with CSV source */}
          {status === "draft" && c.source_type === "csv" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCsvUpload(!showCsvUpload)}
            >
              <Upload className="mr-1 h-4 w-4" />
              Upload CSV
            </Button>
          )}
        </div>
      </div>

      {/* CRM load result message */}
      {crmLoadResult && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
          {crmLoadResult}
        </div>
      )}
      {loadFromCrm.isError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          Failed to load contacts from CRM. Check your CRM connection and try again.
        </div>
      )}

      {/* Retry all failed result */}
      {retryAllFailed.isSuccess && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
          {retryAllFailed.data.retried} contacts reset to pending for retry.
        </div>
      )}

      {/* CSV Upload section */}
      {showCsvUpload && status === "draft" && (
        <Card>
          <CardContent className="pt-6">
            <StepCsvUpload
              campaignId={campaignId}
              tenantId={tenantId}
              onLoadComplete={(loaded) => {
                setShowCsvUpload(false);
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* Tab navigation */}
      <div className="flex gap-1 border-b">
        {([
          { key: "overview" as const, label: "Overview", icon: Play },
          { key: "contacts" as const, label: "Contacts", icon: Users },
          { key: "analytics" as const, label: "Analytics", icon: BarChart3 },
        ]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${activeTab === key
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <>
          {/* Progress bar */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Progress</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  {stats.data ? formatProgress(stats.data.completed_calls, stats.data.total_contacts) : "0%"}
                </span>
                <span className="font-medium tabular-nums">
                  {progressPercent.toFixed(0)}%
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              {/* ETA based on calls_per_minute rate */}
              {status === "running" && stats.data && campaign.data && (() => {
                const remaining = stats.data.total_contacts - stats.data.completed_calls;
                const cpm = campaign.data.calls_per_minute || 1;
                const concurrent = campaign.data.max_concurrent || 1;
                const effectiveRate = Math.min(cpm, concurrent);
                const minutesLeft = Math.ceil(remaining / effectiveRate);
                if (remaining <= 0) return null;
                const hours = Math.floor(minutesLeft / 60);
                const mins = minutesLeft % 60;
                const etaStr = hours > 0 ? `~${hours}h ${mins}m remaining` : `~${mins}m remaining`;
                return (
                  <p className="text-xs text-muted-foreground">{etaStr} ({remaining} contacts at {effectiveRate}/min)</p>
                );
              })()}
            </CardContent>
          </Card>

          {/* Stats cards */}
          <CampaignStatsCards stats={stats.data} isLoading={stats.isLoading} />

          {/* Campaign Configuration */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* Call Settings */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Call Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Source</span>
                  <span className="font-medium capitalize">{c.source_type?.replace("_", " ") || "—"}</span>
                </div>
                {c.from_number && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">From Number</span>
                    <span className="font-mono">{c.from_number}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Concurrent Calls</span>
                  <span>{c.max_concurrent}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Calls/min</span>
                  <span>{c.calls_per_minute}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Max Retries</span>
                  <span>{c.max_retries}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Retry Delay</span>
                  <span>{c.retry_delay_minutes} min</span>
                </div>
                {c.scheduled_at && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Scheduled</span>
                    <span>{formatDateTime(c.scheduled_at)}</span>
                  </div>
                )}
                {c.variant_agent_id && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">A/B Split</span>
                    <span>{c.ab_split_percent}% / {100 - c.ab_split_percent}%</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Source Config */}
            {c.source_config && Object.keys(c.source_config).filter(k => !k.startsWith("_")).length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Source Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {Object.entries(c.source_config)
                    .filter(([k]) => !k.startsWith("_"))
                    .map(([key, value]) => (
                      <div key={key} className="flex justify-between">
                        <span className="text-muted-foreground capitalize">{key.replace(/_/g, " ")}</span>
                        <span className="font-medium">{String(value)}</span>
                      </div>
                    ))}
                </CardContent>
              </Card>
            )}

            {/* Variable Mapping */}
            {c.variable_mapping && Object.keys(c.variable_mapping).length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Variable Mapping</CardTitle>
                  <p className="text-xs text-muted-foreground">CRM fields → Agent variables</p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {Object.entries(c.variable_mapping).map(([varName, crmField]) => (
                      <div key={varName} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                        <code className="text-xs text-muted-foreground">{String(crmField)}</code>
                        <span className="text-muted-foreground">→</span>
                        <code className="text-xs font-medium">{`{{${varName}}}`}</code>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Writeback Mapping */}
            {c.writeback_mapping && Object.keys(c.writeback_mapping).length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Write-Back Mapping</CardTitle>
                  <p className="text-xs text-muted-foreground">Extraction fields → CRM fields</p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {Object.entries(c.writeback_mapping).map(([extractField, crmField]) => (
                      <div key={extractField} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                        <code className="text-xs text-muted-foreground">{extractField}</code>
                        <span className="text-muted-foreground">→</span>
                        <code className="text-xs font-medium">{String(crmField)}</code>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </>
      )}

      {activeTab === "contacts" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contacts</CardTitle>
          </CardHeader>
          <CardContent>
            <CampaignContactsTable campaignId={campaignId} tenantId={tenantId} />
          </CardContent>
        </Card>
      )}

      {activeTab === "analytics" && (
        <CampaignAnalytics campaignId={campaignId} tenantId={tenantId} />
      )}
    </div>
  );
}
