/**
 * Call Detail Modal — shows call metadata, transcript, and audio player.
 *
 * Opened from call history table when a row is clicked.
 * Fetches full call data including transcript via useCall() hook.
 */

"use client";

import { useMemo, useState } from "react";
import {
  Clock,
  Database,
  Hash,
  IndianRupee,
  Loader2,
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  Play,
  RefreshCw,
  User2,
  Wrench,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { useCall, useCallRecordingUrl, useReExtractCall, useExchangeRate, useCallToolExecutions } from "../hooks/use-calls";
import type { Call, CallStatus, TranscriptEntry } from "../types";
import type { ToolExecution } from "../hooks/use-calls";

// ── Status Badge ────────────────────────────────────────────

const STATUS_COLORS: Record<CallStatus, string> = {
  queued: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  ringing:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  in_progress:
    "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  completed:
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  no_answer: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const STATUS_LABELS: Record<CallStatus, string> = {
  queued: "Queued",
  ringing: "Ringing",
  in_progress: "In Progress",
  completed: "Completed",
  failed: "Failed",
  no_answer: "No Answer",
};

const WRITEBACK_STATUS_COLORS: Record<string, string> = {
  pending:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  synced: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  skipped: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

// ── Helpers ─────────────────────────────────────────────────

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatTimestamp(ts: number | string | null, callStart?: string | null): string {
  if (ts === null || ts === undefined) return "";
  // If ts is an ISO string, compute relative seconds from call start
  if (typeof ts === "string") {
    const tsDate = new Date(ts).getTime();
    if (isNaN(tsDate)) return "";
    const base = callStart ? new Date(callStart).getTime() : tsDate;
    const secs = Math.max(0, Math.floor((tsDate - base) / 1000));
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${mins}:${rem.toString().padStart(2, "0")}`;
  }
  // Numeric seconds (legacy)
  const mins = Math.floor(ts / 60);
  const secs = Math.floor(ts % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }).format(new Date(dateStr));
}

// ── Transcript Item ─────────────────────────────────────────

function TranscriptBubble({ entry, callStart }: { entry: TranscriptEntry; callStart?: string | null }) {
  const isUser = entry.speaker === "user";
  return (
    <div
      className={`flex ${isUser ? "justify-start" : "justify-end"} mb-3`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${isUser
          ? "bg-muted text-foreground"
          : "bg-primary text-primary-foreground"
          }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium opacity-75">
            {isUser ? "Caller" : "Agent"}
          </span>
          <span className="text-xs opacity-50">
            {formatTimestamp(entry.timestamp, callStart)}
          </span>
        </div>
        <p className="text-sm">{entry.text}</p>
      </div>
    </div>
  );
}

// ── Metadata Row ────────────────────────────────────────────

// ── Tool Execution Card ─────────────────────────────────────

const TOOL_STATUS_COLORS: Record<string, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  timeout: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

function ToolExecutionCard({ execution }: { execution: ToolExecution }) {
  const [expanded, setExpanded] = useState(false);

  const timestamp = execution.executed_at
    ? new Date(execution.executed_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
    : "";

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Wrench className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-sm font-medium truncate">{execution.tool_name}</span>
          <Badge variant="outline" className="text-xs shrink-0">
            {execution.tool_category}
          </Badge>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-muted-foreground">{execution.duration_ms}ms</span>
          <Badge className={TOOL_STATUS_COLORS[execution.status] ?? TOOL_STATUS_COLORS.error}>
            {execution.status}
          </Badge>
        </div>
      </div>

      {timestamp && (
        <p className="text-xs text-muted-foreground">{timestamp}</p>
      )}

      {execution.error && (
        <p className="text-xs text-red-600 dark:text-red-400">{execution.error}</p>
      )}

      <button
        className="text-xs text-primary hover:underline"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? "Hide details" : "Show details"}
      </button>

      {expanded && (
        <div className="space-y-2">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Arguments</p>
            <pre className="text-xs bg-muted rounded p-2 overflow-x-auto max-h-32">
              {JSON.stringify(execution.arguments, null, 2)}
            </pre>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Result</p>
            <pre className="text-xs bg-muted rounded p-2 overflow-x-auto max-h-32">
              {JSON.stringify(execution.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Meta Row ────────────────────────────────────────────────

function MetaRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
      <span className="text-sm text-muted-foreground w-32">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

// ── Cost Line ───────────────────────────────────────────────

function CostLine({
  label,
  provider,
  model,
  detail,
  usd,
  inrRate,
}: {
  label: string;
  provider?: string | null;
  model?: string | null;
  detail?: string;
  usd: number;
  inrRate: number | null;
}) {
  const providerLabel = [provider, model].filter(Boolean).join(" / ") || "—";
  return (
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <p className="text-xs text-muted-foreground truncate" title={providerLabel}>
          {providerLabel}
        </p>
        {detail && (
          <p className="text-xs text-muted-foreground/70">{detail}</p>
        )}
      </div>
      <span className="text-sm font-mono tabular-nums whitespace-nowrap">
        {inrRate ? `₹${(usd * inrRate).toFixed(4)}` : `$${usd.toFixed(6)}`}
      </span>
    </div>
  );
}

// ── Component ───────────────────────────────────────────────

interface CallDetailModalProps {
  callId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CallDetailModal({
  callId,
  open,
  onOpenChange,
}: CallDetailModalProps) {
  const { data: call, isLoading } = useCall(callId ?? "");
  const { data: recordingData } = useCallRecordingUrl(
    callId,
    !!call?.recording_url,
  );
  const { data: rateData } = useExchangeRate();
  const { data: toolExecutions } = useCallToolExecutions(callId ?? null);
  const reExtract = useReExtractCall();

  const inrRate = rateData ? Number(rateData.rate) : null;

  const extractedEntries = useMemo(() => {
    if (!call?.extracted_data) return [];
    return Object.entries(call.extracted_data);
  }, [call]);

  const groupedExtractedData = useMemo(() => {
    if (!call?.extracted_data) return [];

    const FIELD_CATEGORIES: Record<string, string[]> = {
      "Call Summary": ["call_summary", "key_topics", "caller_intent", "call_outcome"],
      "Success Evaluation": [
        "call_successful",
        "success_score",
        "success_description",
      ],
      "Customer Sentiment": ["customer_sentiment", "customer_frustrated"],
      "Agent Performance": ["script_followed", "agent_tone", "agent_errors"],
      "Action Items": ["action_items", "follow_up_needed"],
      "Caller Info": ["caller_name", "caller_email", "caller_phone"],
      "Healthcare & Clinics": [
        "appointment_booked",
        "appointment_date",
        "appointment_time",
        "appointment_type",
        "doctor_name",
        "insurance_discussed",
        "insurance_provider",
        "symptoms_mentioned",
        "referral_needed",
        "prescription_discussed",
      ],
      "Hospitality & Hotels": [
        "booking_status",
        "booking_type",
        "booking_location",
        "booking_price",
        "check_in_date",
        "check_out_date",
        "guest_count",
        "special_requests",
      ],
      "Real Estate": [
        "property_interest",
        "viewing_scheduled",
        "viewing_date",
        "budget_range",
        "location_preference",
        "buyer_qualified",
        "property_requirements",
      ],
      "Sales & Leads": [
        "sale_completed",
        "lead_qualified",
        "lead_status",
        "revenue_amount",
        "products_discussed",
        "objections_raised",
        "discount_requested",
        "competitor_mentioned",
        "next_step",
      ],
      "Customer Support": [
        "issue_resolved",
        "issue_type",
        "issue_severity",
        "escalation_required",
        "support_ticket_created",
        "resolution_summary",
      ],
      Insurance: [
        "policy_type",
        "claim_filed",
        "claim_number",
        "coverage_question",
        "premium_discussed",
        "renewal_date",
      ],
      "Restaurant & Food": [
        "reservation_made",
        "reservation_date",
        "reservation_time",
        "party_size",
        "dietary_requirements",
        "order_placed",
      ],
      "Quality & Compliance": [
        "compliance_verified",
        "quality_score",
        "supervisor_review_needed",
        "appropriate_greeting",
      ],
      // Legacy aliases
      Appointment: [
        "appointment_scheduled",
        "appointment_cancelled",
        "appointment_rescheduled",
      ],
      "Customer Experience": [
        "csat_score",
        "nps_score",
        "would_recommend",
        "feedback_summary",
      ],
    };

    // Build reverse map: field → category
    const fieldToCategory: Record<string, string> = {};
    for (const [category, fields] of Object.entries(FIELD_CATEGORIES)) {
      for (const field of fields) {
        fieldToCategory[field] = category;
      }
    }

    const groups: Record<string, [string, unknown][]> = {};
    for (const [key, value] of Object.entries(call.extracted_data)) {
      // Skip internal/meta fields and null values
      if (key.startsWith("_")) continue;
      if (value === null || value === undefined) continue;
      const category = fieldToCategory[key] ?? "Other";
      if (!groups[category]) groups[category] = [];
      groups[category].push([key, value]);
    }

    // Sort: defined categories first (in order), then "Other" last
    const categoryOrder = Object.keys(FIELD_CATEGORIES);
    return Object.entries(groups).sort(([a], [b]) => {
      const ai = categoryOrder.indexOf(a);
      const bi = categoryOrder.indexOf(b);
      if (ai === -1 && bi === -1) return a.localeCompare(b);
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    });
  }, [call]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh]">
        {isLoading || !call ? (
          <div className="flex h-60 items-center justify-center">
            <DialogHeader className="sr-only">
              <DialogTitle>Call Details</DialogTitle>
            </DialogHeader>
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {call.direction === "inbound" ? (
                  <PhoneIncoming className="h-5 w-5 text-green-500" />
                ) : (
                  <PhoneOutgoing className="h-5 w-5 text-blue-500" />
                )}
                Call Details
                <Badge className={STATUS_COLORS[call.status as CallStatus]}>
                  {STATUS_LABELS[call.status as CallStatus] ?? call.status}
                </Badge>
              </DialogTitle>
            </DialogHeader>

            <Tabs defaultValue="details" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="transcript">
                  Transcript
                  {call.transcript && call.transcript.length > 0 && (
                    <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                      {call.transcript.length}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="data">Extracted Data</TabsTrigger>
                <TabsTrigger value="tools">
                  Tools
                  {toolExecutions && toolExecutions.length > 0 && (
                    <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                      {toolExecutions.length}
                    </Badge>
                  )}
                </TabsTrigger>
              </TabsList>

              {/* Details Tab */}
              <TabsContent value="details">
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-1">
                    <MetaRow
                      icon={Phone}
                      label="From"
                      value={
                        <span className="font-mono">{call.from_number}</span>
                      }
                    />
                    <MetaRow
                      icon={Phone}
                      label="To"
                      value={
                        <span className="font-mono">{call.to_number}</span>
                      }
                    />
                    <Separator />
                    <MetaRow
                      icon={Clock}
                      label="Duration"
                      value={formatDuration(call.duration_seconds)}
                    />
                    <MetaRow
                      icon={Hash}
                      label="Turns"
                      value={call.turn_count}
                    />
                    <MetaRow
                      icon={Zap}
                      label="Avg Latency"
                      value={
                        call.avg_latency_ms
                          ? `${call.avg_latency_ms}ms`
                          : "—"
                      }
                    />
                    <Separator />

                    {/* ── Cost Breakdown ── */}
                    {call.total_cost ? (
                      <div className="py-2">
                        <div className="flex items-center gap-2 mb-3">
                          <IndianRupee className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-semibold">Cost Breakdown</span>
                        </div>
                        <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                          {/* STT */}
                          {call.stt_cost && (
                            <CostLine
                              label="STT"
                              provider={call.usage_metrics?.stt?.provider}
                              model={call.usage_metrics?.stt?.model}
                              detail={
                                call.usage_metrics?.stt?.audio_seconds != null
                                  ? `${call.usage_metrics.stt.audio_seconds.toFixed(1)}s audio`
                                  : undefined
                              }
                              usd={Number(call.stt_cost)}
                              inrRate={inrRate}
                            />
                          )}
                          {/* LLM */}
                          {call.llm_cost && (
                            <CostLine
                              label="LLM"
                              provider={call.usage_metrics?.llm?.provider}
                              model={call.usage_metrics?.llm?.model}
                              detail={
                                call.usage_metrics?.llm
                                  ? `${(call.usage_metrics.llm.input_tokens ?? 0).toLocaleString()} in / ${(call.usage_metrics.llm.output_tokens ?? 0).toLocaleString()} out tokens`
                                  : undefined
                              }
                              usd={Number(call.llm_cost)}
                              inrRate={inrRate}
                            />
                          )}
                          {/* TTS */}
                          {call.tts_cost && (
                            <CostLine
                              label="TTS"
                              provider={call.usage_metrics?.tts?.provider}
                              model={call.usage_metrics?.tts?.model}
                              detail={
                                call.usage_metrics?.tts?.characters != null
                                  ? `${call.usage_metrics.tts.characters.toLocaleString()} chars`
                                  : undefined
                              }
                              usd={Number(call.tts_cost)}
                              inrRate={inrRate}
                            />
                          )}
                          {/* Telephony */}
                          {call.telephony_cost && (
                            <CostLine
                              label="Telephony"
                              provider={call.usage_metrics?.telephony?.provider}
                              detail={
                                call.usage_metrics?.telephony?.duration_seconds != null
                                  ? `${call.usage_metrics.telephony.duration_seconds.toFixed(1)}s`
                                  : undefined
                              }
                              usd={Number(call.telephony_cost)}
                              inrRate={inrRate}
                            />
                          )}
                          {/* Total */}
                          <Separator />
                          <div className="flex items-center justify-between pt-1">
                            <span className="text-sm font-semibold">Total</span>
                            <span className="text-sm font-bold tabular-nums">
                              {inrRate
                                ? `₹${(Number(call.total_cost) * inrRate).toFixed(4)}`
                                : `$${Number(call.total_cost).toFixed(6)}`}
                            </span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <MetaRow
                        icon={IndianRupee}
                        label="Cost"
                        value="—"
                      />
                    )}

                    <Separator />
                    <MetaRow
                      icon={User2}
                      label="Agent ID"
                      value={
                        <span className="font-mono text-xs">
                          {call.agent_id}
                        </span>
                      }
                    />
                    <MetaRow
                      icon={Clock}
                      label="Started"
                      value={formatDate(call.started_at)}
                    />
                    <MetaRow
                      icon={Clock}
                      label="Ended"
                      value={formatDate(call.ended_at)}
                    />
                    {call.disconnection_reason && (
                      <MetaRow
                        icon={Phone}
                        label="Disconnect"
                        value={call.disconnection_reason}
                      />
                    )}
                    {call.writeback_status && (
                      <>
                        <Separator />
                        <MetaRow
                          icon={Database}
                          label="CRM Sync"
                          value={
                            <Badge
                              className={
                                WRITEBACK_STATUS_COLORS[
                                call.writeback_status
                                ] ?? WRITEBACK_STATUS_COLORS.skipped
                              }
                            >
                              {call.writeback_status}
                            </Badge>
                          }
                        />
                        {call.writeback_status === "failed" &&
                          call.writeback_error && (
                            <MetaRow
                              icon={Zap}
                              label="Sync Error"
                              value={
                                <span className="text-xs text-red-600 dark:text-red-400">
                                  {call.writeback_error}
                                </span>
                              }
                            />
                          )}
                        {call.writeback_completed_at && (
                          <MetaRow
                            icon={Clock}
                            label="Synced At"
                            value={formatDate(call.writeback_completed_at)}
                          />
                        )}
                      </>
                    )}
                    {call.writeback_status && (
                      <MetaRow
                        icon={Database}
                        label="CRM Writeback"
                        value={
                          call.writeback_status === "synced" ? (
                            <span className="text-green-600 dark:text-green-400">
                              ✓ Synced
                              {call.writeback_completed_at &&
                                ` at ${new Date(call.writeback_completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
                            </span>
                          ) : call.writeback_status === "failed" ? (
                            <span className="text-red-600 dark:text-red-400">
                              ✗ Failed{call.writeback_error && `: ${call.writeback_error}`}
                            </span>
                          ) : call.writeback_status === "pending" ? (
                            <span className="text-yellow-600 dark:text-yellow-400">
                              ⏳ Pending
                            </span>
                          ) : call.writeback_status === "skipped" ? (
                            <span className="text-muted-foreground">
                              ⊘ Skipped
                            </span>
                          ) : (
                            <span>{call.writeback_status}</span>
                          )
                        }
                      />
                    )}
                  </div>

                  {/* Audio Player */}
                  {call.recording_url && (
                    <div className="mt-4 rounded-lg border p-4">
                      <p className="text-sm font-medium mb-2 flex items-center gap-2">
                        <Play className="h-4 w-4" />
                        Recording
                      </p>
                      {recordingData?.url ? (
                        <audio
                          controls
                          className="w-full"
                          src={recordingData.url}
                        >
                          <track kind="captions" />
                          Your browser does not support audio playback.
                        </audio>
                      ) : (
                        <p className="text-sm text-muted-foreground">Loading recording…</p>
                      )}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              {/* Transcript Tab */}
              <TabsContent value="transcript">
                <ScrollArea className="h-[400px] pr-4">
                  {call.transcript && call.transcript.length > 0 ? (
                    <div className="space-y-1 py-2">
                      {call.transcript.map((entry, idx) => (
                        <TranscriptBubble
                          key={`${entry.timestamp}-${idx}`}
                          entry={entry}
                          callStart={call.started_at}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                      No transcript available for this call.
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              {/* Extracted Data Tab */}
              <TabsContent value="data">
                <div className="flex items-center justify-end mb-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={reExtract.isPending || !call?.transcript?.length}
                    onClick={() => callId && reExtract.mutate(callId)}
                  >
                    {reExtract.isPending ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    Re-extract
                  </Button>
                </div>
                <ScrollArea className="h-[400px] pr-4">
                  {reExtract.isPending ? (
                    <div className="flex flex-col h-40 items-center justify-center gap-3 text-sm text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <p>Running post-call analysis…</p>
                    </div>
                  ) : groupedExtractedData.length > 0 ? (
                    <div className="space-y-5 py-2">
                      {groupedExtractedData.map(([category, fields]) => (
                        <div key={category}>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {category}
                          </h4>
                          <div className="space-y-1.5">
                            {fields.map(([key, value]) => {
                              const label = key
                                .replace(/_/g, " ")
                                .replace(/\b\w/g, (c: string) => c.toUpperCase());

                              // Long text fields get a stacked layout
                              const isLongText =
                                typeof value === "string" && value.length > 60;
                              const isArray = Array.isArray(value);

                              if (isLongText) {
                                return (
                                  <div
                                    key={key}
                                    className="rounded border bg-muted/30 px-3 py-2.5"
                                  >
                                    <div className="text-xs font-semibold text-muted-foreground mb-1">
                                      {label}
                                    </div>
                                    <div className="text-sm leading-relaxed">
                                      {String(value)}
                                    </div>
                                  </div>
                                );
                              }

                              if (isArray) {
                                return (
                                  <div
                                    key={key}
                                    className="rounded border bg-muted/30 px-3 py-2.5"
                                  >
                                    <div className="text-xs font-semibold text-muted-foreground mb-1.5">
                                      {label}
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                      {(value as unknown[]).map((item, i) => (
                                        <span
                                          key={i}
                                          className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
                                        >
                                          {String(item)}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                );
                              }

                              // Objects get a mini key-value grid
                              if (typeof value === "object" && value !== null && !Array.isArray(value)) {
                                const entries = Object.entries(value as Record<string, unknown>).filter(
                                  ([, v]) => v !== null && v !== undefined
                                );
                                return (
                                  <div
                                    key={key}
                                    className="rounded border bg-muted/30 px-3 py-2.5"
                                  >
                                    <div className="text-xs font-semibold text-muted-foreground mb-1.5">
                                      {label}
                                    </div>
                                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                                      {entries.map(([k, v]) => (
                                        <div key={k} className="flex justify-between text-sm">
                                          <span className="text-muted-foreground">
                                            {k.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                                          </span>
                                          <span className="font-medium text-right">
                                            {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                );
                              }

                              // Short values: side-by-side layout
                              let displayValue: React.ReactNode;
                              if (typeof value === "boolean") {
                                displayValue = (
                                  <span
                                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${value
                                      ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/20"
                                      : "bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/20"
                                      }`}
                                  >
                                    {value ? "Yes" : "No"}
                                  </span>
                                );
                              } else if (
                                typeof value === "number" &&
                                key.includes("score")
                              ) {
                                displayValue = (
                                  <span className="font-semibold tabular-nums">
                                    {value}
                                    <span className="text-muted-foreground font-normal">
                                      /10
                                    </span>
                                  </span>
                                );
                              } else {
                                displayValue = String(value ?? "—");
                              }

                              return (
                                <div
                                  key={key}
                                  className="flex items-center justify-between rounded border px-3 py-2"
                                >
                                  <span className="text-sm text-muted-foreground">
                                    {label}
                                  </span>
                                  <span className="text-sm text-right">
                                    {displayValue}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : call?.status === "completed" &&
                    Object.keys(call?.extracted_data ?? {}).length === 0 &&
                    !call?.extraction_completed_at ? (
                    <div className="flex flex-col h-40 items-center justify-center gap-3 text-sm text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <p>Post-call analysis in progress…</p>
                    </div>
                  ) : (
                    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                      No extracted data available.
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              {/* Tools Tab */}
              <TabsContent value="tools">
                <ScrollArea className="h-[400px] pr-4">
                  {toolExecutions && toolExecutions.length > 0 ? (
                    <div className="space-y-3">
                      {toolExecutions.map((exec) => (
                        <ToolExecutionCard key={exec.id} execution={exec} />
                      ))}
                    </div>
                  ) : (
                    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                      No tool calls were made during this call.
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>
            </Tabs>

            {/* Footer Actions */}
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
              >
                Close
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
