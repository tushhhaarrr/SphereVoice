"use client";

/**
 * Test Call Panel — Browser-based voice call OR outbound phone call
 * to test an agent.
 *
 * Browser mode: WebRTC via LiveKit (existing).
 * Phone mode: Real PSTN call via Plivo — pick a FROM number and
 * dial your phone to hear the agent live.
 *
 * Phase 6: Full connection + real-time transcript display.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Gauge,
  Globe,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  PhoneCall,
  PhoneOutgoing,
  Loader2,
  AlertTriangle,
  Radio,
  User2,
  Volume2,
  Brain,
  MessageSquare,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TranscriptDisplay,
  useTestCall,
  extractVariables,
  type PromptVariable,
  type TestCallLatencyState,
  type TestCallStatus,
} from "@/modules/agents";
import { useOutboundTestCall } from "../hooks/use-outbound-test-call";
import { usePhoneNumbers } from "@/modules/phone-numbers";
import { TestPersonaSelector } from "./test-personas";
import {
  useCrmIntegrations,
  useCrmContacts,
  useCrmLeads,
  type ZohoRecord,
} from "@/modules/integrations";
import { Search, Database, Link2, X } from "lucide-react";

import type { CrmReadMapping } from "./agent-crm-tab";
import type { AgentSettings } from "./agent-settings";

type CallMode = "browser" | "phone";

// ── Helpers ─────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatLatency(ms: number | null): string {
  if (ms === null) return "--";
  return `${Math.round(ms)}ms`;
}

const STATUS_CONFIG: Record<
  TestCallStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  idle: {
    label: "Ready",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    icon: <Phone className="h-3 w-3" />,
  },
  connecting: {
    label: "Connecting...",
    color:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  connected: {
    label: "In Call",
    color:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    icon: <Radio className="h-3 w-3" />,
  },
  disconnecting: {
    label: "Ending...",
    color:
      "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
  },
  ended: {
    label: "Call Ended",
    color: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    icon: <PhoneOff className="h-3 w-3" />,
  },
  error: {
    label: "Error",
    color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    icon: <AlertTriangle className="h-3 w-3" />,
  },
};

// ── Component ───────────────────────────────────────────────

interface TestCallPanelProps {
  agentId: string;
  agentSettings?: AgentSettings;
  prompt?: string;
  variables?: PromptVariable[];
  crmReadMapping?: CrmReadMapping;
}

/** System variables auto-filled at runtime — never need a default value. */
const AUTO_FILLED_VARS = new Set([
  "current_date", "current_time", "current_datetime",
  "caller_number", "caller_name", "agent_name", "company_name",
]);

/** CRM context fields available for injection during test calls. */
const FALLBACK_CRM_CONTEXT_FIELDS = [
  { key: "lead_name", label: "Contact Name", placeholder: "Priya Sharma" },
  { key: "lead_email", label: "Email", placeholder: "priya@example.com" },
  { key: "lead_phone", label: "Phone", placeholder: "+919876543210" },
  { key: "lead_company", label: "Company", placeholder: "TechVentures" },
  { key: "deal_stage", label: "Deal Stage", placeholder: "Negotiation" },
  { key: "caller_name", label: "Caller Name", placeholder: "Priya Sharma" },
] as const;

// Country codes for the dropdown — India first, then common ones alphabetically
const COUNTRY_CODES = [
  { code: "+91", label: "India", flag: "🇮🇳" },
  { code: "+1", label: "US / Canada", flag: "🇺🇸" },
  { code: "+44", label: "UK", flag: "🇬🇧" },
  { code: "+61", label: "Australia", flag: "🇦🇺" },
  { code: "+971", label: "UAE", flag: "🇦🇪" },
  { code: "+966", label: "Saudi Arabia", flag: "🇸🇦" },
  { code: "+65", label: "Singapore", flag: "🇸🇬" },
  { code: "+49", label: "Germany", flag: "🇩🇪" },
  { code: "+33", label: "France", flag: "🇫🇷" },
  { code: "+81", label: "Japan", flag: "🇯🇵" },
  { code: "+86", label: "China", flag: "🇨🇳" },
  { code: "+55", label: "Brazil", flag: "🇧🇷" },
  { code: "+52", label: "Mexico", flag: "🇲🇽" },
  { code: "+62", label: "Indonesia", flag: "🇮🇩" },
  { code: "+63", label: "Philippines", flag: "🇵🇭" },
  { code: "+234", label: "Nigeria", flag: "🇳🇬" },
  { code: "+254", label: "Kenya", flag: "🇰🇪" },
  { code: "+27", label: "South Africa", flag: "🇿🇦" },
  { code: "+82", label: "South Korea", flag: "🇰🇷" },
  { code: "+39", label: "Italy", flag: "🇮🇹" },
  { code: "+34", label: "Spain", flag: "🇪🇸" },
  { code: "+31", label: "Netherlands", flag: "🇳🇱" },
  { code: "+46", label: "Sweden", flag: "🇸🇪" },
  { code: "+47", label: "Norway", flag: "🇳🇴" },
  { code: "+353", label: "Ireland", flag: "🇮🇪" },
  { code: "+64", label: "New Zealand", flag: "🇳🇿" },
  { code: "+60", label: "Malaysia", flag: "🇲🇾" },
  { code: "+66", label: "Thailand", flag: "🇹🇭" },
  { code: "+84", label: "Vietnam", flag: "🇻🇳" },
  { code: "+880", label: "Bangladesh", flag: "🇧🇩" },
  { code: "+92", label: "Pakistan", flag: "🇵🇰" },
  { code: "+94", label: "Sri Lanka", flag: "🇱🇰" },
  { code: "+977", label: "Nepal", flag: "🇳🇵" },
] as const;

/** Map a CRM record's fields into the dynamic_variables keys.
 * Uses the saved crmReadMapping when available, otherwise falls back
 * to sensible defaults for common field names.
 */
function crmRecordToContext(
  record: ZohoRecord,
  module: string,
  readMapping?: CrmReadMapping,
): Record<string, string> {
  const ctx: Record<string, string> = {
    // Always inject these for CRM writeback targeting
    caller_crm_id: record.id,
    caller_crm_module: module,
  };

  if (readMapping && Object.keys(readMapping.mapping).length > 0) {
    // Use saved read mapping: variable_name → crm_field_api_name
    for (const [varName, crmField] of Object.entries(readMapping.mapping)) {
      const val = (record as Record<string, unknown>)[crmField];
      ctx[varName] = val != null ? String(val) : "";
    }
    // Always set caller_name from Full_Name if not mapped
    if (!ctx.caller_name) {
      ctx.caller_name = record.Full_Name ?? `${record.First_Name ?? ""} ${record.Last_Name ?? ""}`.trim();
    }
  } else {
    // Fallback: hardcoded defaults for common fields
    ctx.lead_name = record.Full_Name ?? `${record.First_Name ?? ""} ${record.Last_Name ?? ""}`.trim();
    ctx.lead_email = record.Email ?? "";
    ctx.lead_phone = record.Phone ?? record.Mobile ?? "";
    ctx.lead_company = record.Company ?? record.Account_Name ?? "";
    ctx.deal_stage = record.Stage ?? record.Lead_Status ?? "";
    ctx.caller_name = record.Full_Name ?? `${record.First_Name ?? ""} ${record.Last_Name ?? ""}`.trim();
  }
  return ctx;
}

export function TestCallPanel({ agentId, agentSettings, prompt, variables, crmReadMapping }: TestCallPanelProps) {
  const [callMode, setCallMode] = useState<CallMode>("browser");
  const [countryCode, setCountryCode] = useState("+91");
  const [phoneDigits, setPhoneDigits] = useState("");
  const [fromNumber, setFromNumber] = useState("");
  const [showCrmPanel, setShowCrmPanel] = useState(false);

  // CRM record picker state
  const [showCrmPicker, setShowCrmPicker] = useState(false);
  const [crmModule, setCrmModule] = useState<"Contacts" | "Leads">("Leads");
  const [crmSearch, setCrmSearch] = useState("");
  const [debouncedCrmSearch, setDebouncedCrmSearch] = useState("");
  const [selectedCrmRecord, setSelectedCrmRecord] = useState<{
    record: ZohoRecord;
    module: string;
  } | null>(null);

  // Debounce CRM search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedCrmSearch(crmSearch), 400);
    return () => clearTimeout(timer);
  }, [crmSearch]);

  // Check if CRM is connected
  const { data: crmIntegrations } = useCrmIntegrations();
  const isCrmConnected = crmIntegrations?.integrations?.some(
    (i) => i.status === "connected",
  ) ?? false;

  // CRM record search queries (only when picker is open)
  const crmContacts = useCrmContacts({
    search: debouncedCrmSearch || undefined,
    perPage: 8,
    enabled: isCrmConnected && showCrmPicker && crmModule === "Contacts",
  });
  const crmLeads = useCrmLeads({
    search: debouncedCrmSearch || undefined,
    perPage: 8,
    enabled: isCrmConnected && showCrmPicker && crmModule === "Leads",
  });
  const crmRecords = (crmModule === "Contacts" ? crmContacts : crmLeads).data?.data ?? [];
  const crmLoading = (crmModule === "Contacts" ? crmContacts : crmLeads).isLoading;
  const [crmContext, setCrmContext] = useState<Record<string, string>>({});

  // Combine country code + digits into full E.164 number
  const toNumber = phoneDigits ? `${countryCode}${phoneDigits.replace(/^0+/, "")}` : "";

  // Browser-based test call (WebRTC)
  const {
    status,
    duration,
    error,
    roomName,
    participantCount,
    callId,
    transcript,
    callStartTime,
    latency,
    startCall,
    endCall,
    toggleMute,
    isMuted,
  } = useTestCall(agentId);

  // Phone-based outbound test call (Plivo PSTN)
  const outbound = useOutboundTestCall(agentId);

  // Fetch tenant's active phone numbers for the FROM dropdown
  const { data: phoneNumbersData } = usePhoneNumbers({ status: "active", limit: 50 });
  const phoneNumbers = phoneNumbersData?.numbers ?? [];

  // Auto-select the default outbound number when data loads
  useEffect(() => {
    if (fromNumber || phoneNumbers.length === 0) return;
    const defaultNum = phoneNumbers.find((pn) => pn.is_default_outbound);
    if (defaultNum) {
      setFromNumber(defaultNum.phone_number);
    }
  }, [phoneNumbers, fromNumber]);

  const statusConfig = STATUS_CONFIG[status];
  const isActive = status === "connected";
  const isEnded = status === "ended";
  const isTransitioning = status === "connecting" || status === "disconnecting";
  const hasTranscript = transcript.length > 0;
  const showSessionView = isActive || isEnded || isTransitioning || hasTranscript || Boolean(error);

  // Detect variables used in prompt that have no default value.
  // CRM variables are populated from CRM data at campaign runtime — they
  // should NOT be shown as "missing" warnings. We split them into two lists
  // so the UI can show an info note for CRM vars and a warning for truly missing ones.
  const { missingVars, crmVars } = useMemo(() => {
    if (!prompt) return { missingVars: [] as string[], crmVars: [] as string[] };
    const used = extractVariables(prompt);
    const missing: string[] = [];
    const crm: string[] = [];
    for (const name of used) {
      if (AUTO_FILLED_VARS.has(name)) continue;
      const v = variables?.find((av) => av.name === name);
      if (v?.category === "crm") {
        crm.push(name);
      } else if (!v || !v.defaultValue) {
        missing.push(name);
      }
    }
    return { missingVars: missing, crmVars: crm };
  }, [prompt, variables]);

  // Build CRM context fields dynamically from the agent's actual CRM variables.
  // Falls back to generic fields when no CRM variables are detected.
  const crmContextFields = useMemo(() => {
    if (crmVars.length > 0) {
      return crmVars.map((name) => ({
        key: name,
        label: name.replace(/_/g, " "),
        placeholder: `Enter ${name.replace(/_/g, " ").toLowerCase()}`,
      }));
    }
    return FALLBACK_CRM_CONTEXT_FIELDS.map((f) => ({
      key: f.key,
      label: f.label,
      placeholder: f.placeholder,
    }));
  }, [crmVars]);

  const handleCallToggle = useCallback(async () => {
    if (isActive || isTransitioning) {
      await endCall();
    } else {
      const vars = Object.fromEntries(
        Object.entries(crmContext).filter(([, v]) => v.trim() !== "")
      );
      await startCall(Object.keys(vars).length > 0 ? vars : undefined);
    }
  }, [isActive, isTransitioning, startCall, endCall, crmContext]);

  const handleNewCall = useCallback(async () => {
    const vars = Object.fromEntries(
      Object.entries(crmContext).filter(([, v]) => v.trim() !== "")
    );
    await startCall(Object.keys(vars).length > 0 ? vars : undefined);
  }, [startCall, crmContext]);

  // Phone mode handlers
  const handlePhoneCall = useCallback(async () => {
    if (!fromNumber || !toNumber) return;
    await outbound.startCall(fromNumber, toNumber);
  }, [fromNumber, toNumber, outbound]);

  const handlePhoneEndCall = useCallback(async () => {
    await outbound.endCall();
  }, [outbound]);

  const handlePhoneNewCall = useCallback(async () => {
    if (!fromNumber || !toNumber) return;
    await outbound.startCall(fromNumber, toNumber);
  }, [fromNumber, toNumber, outbound]);

  const isPhoneActive = outbound.status === "ringing" || outbound.status === "in-progress";
  const isPhoneDialing = outbound.status === "dialing";
  const isPhoneEnded = outbound.status === "completed";
  const isPhoneFailed = outbound.status === "failed";
  const canStartPhoneCall = fromNumber && phoneDigits.length >= 6 && !isPhoneActive && !isPhoneDialing;

  // Mode toggle (disabled while a call is active)
  const canSwitchMode = !isActive && !isTransitioning && !isPhoneActive && !isPhoneDialing;

  return (
    <div className="flex h-full flex-col rounded-xl border bg-background">
      <div className="flex min-h-0 flex-1 flex-col space-y-3 p-3">
        {/* Mode Toggle */}
        <div className="flex items-center gap-1 rounded-lg bg-muted/50 p-0.5">
          <button
            type="button"
            onClick={() => canSwitchMode && setCallMode("browser")}
            disabled={!canSwitchMode}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${callMode === "browser"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
              } disabled:opacity-50`}
          >
            <Mic className="h-3 w-3" />
            Browser
          </button>
          <button
            type="button"
            onClick={() => canSwitchMode && setCallMode("phone")}
            disabled={!canSwitchMode}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${callMode === "phone"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
              } disabled:opacity-50`}
          >
            <PhoneOutgoing className="h-3 w-3" />
            Phone Call
          </button>
        </div>

        {callMode === "browser" ? (
          /* ── Browser Mode (existing WebRTC) ── */
          <>
            {showSessionView ? (
              <>
                <div className="flex items-center gap-2">
                  <Badge className={statusConfig.color}>
                    <span className="mr-1">{statusConfig.icon}</span>
                    {statusConfig.label}
                  </Badge>
                  {(isActive || hasTranscript) && (
                    <span className="font-mono text-sm font-semibold tabular-nums">
                      {formatDuration(duration)}
                    </span>
                  )}
                  {(isActive || hasTranscript) && participantCount > 0 && (
                    <span className="text-xs text-muted-foreground">
                      · {participantCount} participant{participantCount !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                {isEnded && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                      <PhoneOff className="h-4 w-4 flex-shrink-0" />
                      <span>The call has ended. Start a new call to continue testing.</span>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950">
                    <div className="flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
                      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                      <span>{error}</span>
                    </div>
                  </div>
                )}

                {(isActive || latency.turnId !== null) && (
                  <LatencyPanel latency={latency} />
                )}

                {(isActive || hasTranscript) && (
                  <div className="min-h-0 flex-1">
                    <TranscriptDisplay
                      entries={transcript}
                      callStartTime={callStartTime}
                      maxHeight="100%"
                    />
                  </div>
                )}

                <div className="flex items-center justify-center gap-3 pt-1">
                  {isActive && (
                    <Button
                      variant={isMuted ? "destructive" : "outline"}
                      size="icon"
                      onClick={toggleMute}
                      title={isMuted ? "Unmute" : "Mute"}
                      className="h-11 w-11 rounded-full"
                    >
                      {isMuted ? (
                        <MicOff className="h-4 w-4" />
                      ) : (
                        <Mic className="h-4 w-4" />
                      )}
                    </Button>
                  )}

                  <Button
                    variant={isActive ? "destructive" : "default"}
                    size="lg"
                    onClick={isEnded ? handleNewCall : handleCallToggle}
                    disabled={isTransitioning}
                    className="min-w-[148px] rounded-full"
                  >
                    {isTransitioning ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {status === "connecting" ? "Connecting..." : "Ending..."}
                      </>
                    ) : isActive ? (
                      <>
                        <PhoneOff className="mr-2 h-4 w-4" />
                        End Call
                      </>
                    ) : isEnded ? (
                      <>
                        <Phone className="mr-2 h-4 w-4" />
                        Start New Call
                      </>
                    ) : (
                      <>
                        <Phone className="mr-2 h-4 w-4" />
                        Test Again
                      </>
                    )}
                  </Button>
                </div>

                {(roomName || callId) && (
                  <div className="rounded-lg border bg-muted/20 p-3 text-[11px] text-muted-foreground">
                    {roomName ? <div>Room: <span className="font-mono">{roomName}</span></div> : null}
                    {callId ? <div>Call: <span className="font-mono">{callId}</span></div> : null}
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col gap-2 p-1">
                {crmVars.length > 0 && (
                  <div className="flex items-center gap-2 rounded-md border border-violet-500/25 bg-violet-50/60 px-2.5 py-1.5 text-[11px] text-violet-700 dark:border-violet-500/20 dark:bg-violet-950/25 dark:text-violet-300">
                    <Database className="h-3 w-3 shrink-0" />
                    <span>
                      <span className="font-medium">{crmVars.length} CRM variable{crmVars.length !== 1 ? "s" : ""}</span>
                      {" — filled from CRM at call time. "}
                      <button
                        type="button"
                        onClick={() => setShowCrmPanel(true)}
                        className="underline underline-offset-2 hover:text-violet-900 dark:hover:text-violet-200"
                      >
                        Simulate below
                      </button>
                    </span>
                  </div>
                )}

                {missingVars.length > 0 && (
                  <div className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-50/60 px-2.5 py-1.5 text-[11px] text-amber-700 dark:border-amber-500/25 dark:bg-amber-950/30 dark:text-amber-300">
                    <AlertTriangle className="h-3 w-3 shrink-0" />
                    <span>
                      <span className="font-medium">{missingVars.length} variable{missingVars.length !== 1 ? "s" : ""} without defaults</span>
                      {" — set in Prompt tab: "}
                      {missingVars.slice(0, 3).map((name, i) => (
                        <span key={name}>
                          {i > 0 && ", "}
                          <code className="font-mono text-[10px]">{name}</code>
                        </span>
                      ))}
                      {missingVars.length > 3 && <span>{` +${missingVars.length - 3} more`}</span>}
                    </span>
                  </div>
                )}

                {/* CRM Context Panel */}
                <div className="rounded-lg border">
                  <button
                    type="button"
                    onClick={() => setShowCrmPanel(!showCrmPanel)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showCrmPanel ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    <User2 className="h-3 w-3" />
                    CRM Context
                    {Object.values(crmContext).some((v) => v.trim()) && (
                      <Badge variant="secondary" className="ml-auto text-[10px] px-1.5 py-0">
                        {Object.values(crmContext).filter((v) => v.trim()).length} fields
                      </Badge>
                    )}
                  </button>
                  {showCrmPanel && (
                    <div className="space-y-3 border-t px-3 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[10px] text-muted-foreground">
                          Inject CRM data so the agent greets by name, references company, etc.
                        </p>
                        <div className="flex items-center gap-1">
                          {isCrmConnected && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-6 text-[10px] gap-1"
                              onClick={() => setShowCrmPicker(!showCrmPicker)}
                              disabled={isActive}
                            >
                              <Database className="h-3 w-3" />
                              {selectedCrmRecord ? "Change" : "Pick from CRM"}
                            </Button>
                          )}
                          <TestPersonaSelector
                            onSelect={(persona) => {
                              setCrmContext(persona.variables);
                              setSelectedCrmRecord(null);
                            }}
                            disabled={isActive}
                          />
                        </div>
                      </div>

                      {/* Selected CRM record indicator */}
                      {selectedCrmRecord && (
                        <div className="flex items-center gap-2 rounded-md border bg-muted/50 px-2.5 py-1.5">
                          <Link2 className="h-3 w-3 text-muted-foreground shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-[11px] font-medium truncate">
                              {selectedCrmRecord.record.Full_Name ?? selectedCrmRecord.record.id}
                            </p>
                            <p className="text-[10px] text-muted-foreground">
                              {selectedCrmRecord.module} &middot; Writeback enabled
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5 text-muted-foreground hover:text-destructive"
                            onClick={() => {
                              setSelectedCrmRecord(null);
                              setCrmContext({});
                            }}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      )}

                      {/* CRM Record Picker (inline) */}
                      {showCrmPicker && (
                        <div className="rounded-md border bg-muted/50 p-2 space-y-2">
                          <div className="flex items-center gap-2">
                            <Select
                              value={crmModule}
                              onValueChange={(v) => setCrmModule(v as "Contacts" | "Leads")}
                            >
                              <SelectTrigger className="h-7 text-[11px] w-24">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="Leads">Leads</SelectItem>
                                <SelectItem value="Contacts">Contacts</SelectItem>
                              </SelectContent>
                            </Select>
                            <div className="relative flex-1">
                              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                              <Input
                                className="h-7 text-xs pl-7"
                                placeholder="Search by name, email, phone..."
                                value={crmSearch}
                                onChange={(e) => setCrmSearch(e.target.value)}
                              />
                            </div>
                          </div>
                          <div className="max-h-[180px] overflow-y-auto space-y-1">
                            {crmLoading ? (
                              <div className="flex items-center justify-center py-3 text-xs text-muted-foreground">
                                <Loader2 className="h-3 w-3 animate-spin mr-1.5" />
                                Searching...
                              </div>
                            ) : crmRecords.length === 0 ? (
                              <p className="text-xs text-muted-foreground text-center py-3">
                                {debouncedCrmSearch ? "No records found" : "Type to search"}
                              </p>
                            ) : (
                              crmRecords.map((record) => (
                                <button
                                  key={record.id}
                                  type="button"
                                  className="w-full flex items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-accent transition-colors"
                                  onClick={() => {
                                    const ctx = crmRecordToContext(record, crmModule, crmReadMapping);
                                    setCrmContext(ctx);
                                    setSelectedCrmRecord({ record, module: crmModule });
                                    setShowCrmPicker(false);
                                    setCrmSearch("");
                                  }}
                                >
                                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-foreground shrink-0">
                                    {(record.Full_Name ?? record.First_Name ?? "?")[0]?.toUpperCase()}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <p className="text-[11px] font-medium truncate">
                                      {record.Full_Name ?? (`${record.First_Name ?? ""} ${record.Last_Name ?? ""}`.trim() || "Unnamed")}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground truncate">
                                      {[record.Company, record.Email].filter(Boolean).join(" · ") || record.Phone || record.id}
                                    </p>
                                  </div>
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-2">
                        {crmContextFields.map((field) => (
                          <div key={field.key} className="space-y-1">
                            <Label className="text-[10px] text-muted-foreground">
                              {field.label}
                            </Label>
                            <Input
                              className="h-7 text-xs"
                              placeholder={field.placeholder}
                              value={crmContext[field.key] ?? ""}
                              onChange={(e) =>
                                setCrmContext((prev) => ({
                                  ...prev,
                                  [field.key]: e.target.value,
                                }))
                              }
                              disabled={isActive}
                            />
                          </div>
                        ))}
                      </div>
                      {Object.values(crmContext).some((v) => v.trim()) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 text-[10px] text-muted-foreground"
                          onClick={() => setCrmContext({})}
                        >
                          Clear all
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                      <Mic className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Test your agent</p>
                      <p className="text-xs text-muted-foreground">
                        Browser audio call to validate voice and flow
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={handleCallToggle}
                    disabled={isTransitioning}
                    className="gap-2 rounded-lg"
                  >
                    {isTransitioning ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      <>
                        <Phone className="h-4 w-4" />
                        Start Test Call
                      </>
                    )}
                  </Button>
                </div>

                {agentSettings && (
                  <>
                    <Separator />
                    <ConfigSummary settings={agentSettings} />
                  </>
                )}
              </div>
            )}
          </>
        ) : (
          /* ── Phone Mode (outbound PSTN via Plivo) ── */
          <>
            {isPhoneActive || isPhoneDialing || isPhoneEnded || isPhoneFailed ? (
              /* Active / completed phone call state */
              <>
                <div className="flex items-center gap-2">
                  <Badge className={
                    isPhoneDialing ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300" :
                      outbound.status === "ringing" ? "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300" :
                        outbound.status === "in-progress" ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" :
                          isPhoneEnded ? "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300" :
                            "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                  }>
                    <span className="mr-1">
                      {isPhoneDialing ? <Loader2 className="h-3 w-3 animate-spin" /> :
                        outbound.status === "ringing" ? <PhoneCall className="h-3 w-3" /> :
                          outbound.status === "in-progress" ? <Radio className="h-3 w-3" /> :
                            isPhoneEnded ? <PhoneOff className="h-3 w-3" /> :
                              <AlertTriangle className="h-3 w-3" />}
                    </span>
                    {isPhoneDialing ? "Dialing..." :
                      outbound.status === "ringing" ? "Ringing" :
                        outbound.status === "in-progress" ? "In Call" :
                          isPhoneEnded ? "Call Ended" : "Failed"}
                  </Badge>
                  {(isPhoneActive || isPhoneEnded) && (
                    <span className="font-mono text-sm font-semibold tabular-nums">
                      {formatDuration(outbound.duration)}
                    </span>
                  )}
                </div>

                <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <PhoneOutgoing className="h-3.5 w-3.5" />
                    <span>{fromNumber} → {toNumber}</span>
                  </div>
                </div>

                {isPhoneEnded && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                      <PhoneOff className="h-4 w-4 flex-shrink-0" />
                      <span>The call has ended. Start a new call to continue testing.</span>
                    </div>
                  </div>
                )}

                {outbound.error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950">
                    <div className="flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
                      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                      <span>{outbound.error}</span>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-center gap-3 pt-1">
                  {isPhoneActive ? (
                    <Button
                      variant="destructive"
                      size="lg"
                      onClick={handlePhoneEndCall}
                      className="min-w-[148px] rounded-full"
                    >
                      <PhoneOff className="mr-2 h-4 w-4" />
                      End Call
                    </Button>
                  ) : (
                    <Button
                      size="lg"
                      onClick={handlePhoneNewCall}
                      disabled={!canStartPhoneCall}
                      className="min-w-[148px] rounded-full"
                    >
                      <Phone className="mr-2 h-4 w-4" />
                      Call Again
                    </Button>
                  )}
                </div>

                {outbound.callId && (
                  <div className="rounded-lg border bg-muted/20 p-3 text-[11px] text-muted-foreground">
                    <div>Call: <span className="font-mono">{outbound.callId}</span></div>
                  </div>
                )}
              </>
            ) : (
              /* Pre-call phone setup */
              <div className="flex flex-col gap-4 p-1">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                    <PhoneOutgoing className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Test via phone call</p>
                    <p className="text-xs text-muted-foreground">
                      Call your phone to hear the agent on a real line
                    </p>
                  </div>
                </div>

                {phoneNumbers.length === 0 ? (
                  <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-300">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>No phone numbers available. Add a phone number in the Phone Numbers section first.</span>
                  </div>
                ) : (
                  <>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Call from</label>
                      <Select value={fromNumber} onValueChange={setFromNumber}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a phone number" />
                        </SelectTrigger>
                        <SelectContent>
                          {phoneNumbers.map((pn) => (
                            <SelectItem key={pn.id} value={pn.phone_number}>
                              {pn.phone_number}
                              {pn.provider_name ? ` (${pn.provider_name})` : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">Call to</label>
                      <div className="flex gap-2">
                        <Select value={countryCode} onValueChange={setCountryCode}>
                          <SelectTrigger className="w-[145px] shrink-0">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {COUNTRY_CODES.map((c) => (
                              <SelectItem key={c.code} value={c.code}>
                                {c.flag} {c.code} {c.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input
                          type="tel"
                          placeholder="9876543210"
                          value={phoneDigits}
                          onChange={(e) => setPhoneDigits(e.target.value.replace(/[^\d]/g, ""))}
                          className="flex-1 font-mono"
                        />
                      </div>
                      {phoneDigits && (
                        <p className="text-[10px] text-muted-foreground font-mono">
                          Will dial: {toNumber}
                        </p>
                      )}
                    </div>

                    <Button
                      onClick={handlePhoneCall}
                      disabled={!canStartPhoneCall}
                      className="gap-2 rounded-lg"
                    >
                      <PhoneOutgoing className="h-4 w-4" />
                      Call Now
                    </Button>
                  </>
                )}

                {agentSettings && (
                  <>
                    <Separator />
                    <ConfigSummary settings={agentSettings} />
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function LatencyPanel({ latency }: { latency: TestCallLatencyState }) {
  const services = [latency.services.stt, latency.services.llm, latency.services.tts];

  return (
    <div className="space-y-2">
      {/* E2E summary bar */}
      <div className="flex items-center justify-between rounded-lg border bg-muted/20 px-3 py-1.5">
        <div className="flex items-center gap-2">
          <Gauge className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">E2E</span>
          <span className="font-mono text-sm font-semibold tabular-nums">
            {formatLatency(latency.pipelineE2eLatencyMs)}
          </span>
        </div>
        <Badge variant="outline" className="gap-1 font-mono text-[10px] h-5">
          Turn {latency.turnId ?? "--"}
        </Badge>
      </div>

      {/* Per-service breakdown */}
      <div className="space-y-1.5">
        {services.map((service) => {
          const hasData = service.responseLatencyMs !== null || service.ttfbLatencyMs !== null;
          return (
            <div
              key={service.stage}
              className="rounded-lg border px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {service.label}
                  </span>
                  {service.processor && (
                    <span className="truncate text-[10px] text-muted-foreground">
                      {service.processor}
                      {service.model ? ` · ${service.model}` : ""}
                    </span>
                  )}
                </div>
                {!hasData && (
                  <span className="text-[10px] text-muted-foreground">waiting…</span>
                )}
              </div>
              {hasData && (
                <div className="mt-1 flex gap-4">
                  <MetricChip label="TTFB" value={service.ttfbLatencyMs} />
                  <MetricChip label="Response" value={service.responseLatencyMs} />
                  <MetricChip label="Processing" value={service.processingLatencyMs} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MetricChip({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null;
  const isHigh = value > 2000;
  const isMed = value > 500 && !isHigh;
  const colorClass = isHigh
    ? "text-red-600 dark:text-red-400"
    : isMed
      ? "text-yellow-600 dark:text-yellow-400"
      : "text-green-600 dark:text-green-400";

  return (
    <div className="text-center">
      <div className={`font-mono text-xs font-semibold tabular-nums ${colorClass}`}>
        {formatLatency(value)}
      </div>
      <div className="text-[9px] text-muted-foreground">{label}</div>
    </div>
  );
}

function ConfigSummary({ settings }: { settings: AgentSettings }) {
  const items = [
    {
      icon: <Globe className="h-3.5 w-3.5" />,
      label: "Language",
      value: settings.voiceLanguage.language?.toUpperCase() || "Not set",
    },
    {
      icon: <Volume2 className="h-3.5 w-3.5" />,
      label: "TTS",
      value: settings.voiceLanguage.ttsProvider || "Not set",
    },
    {
      icon: <MessageSquare className="h-3.5 w-3.5" />,
      label: "STT",
      value: settings.transcription.sttProvider || "Not set",
    },
    {
      icon: <Brain className="h-3.5 w-3.5" />,
      label: "LLM",
      value: settings.llm.model || settings.llm.provider || "Not set",
    },
  ];

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-muted-foreground">Active Configuration</p>
      <div className="grid grid-cols-2 gap-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2"
          >
            <span className="text-muted-foreground">{item.icon}</span>
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">{item.label}</p>
              <p className="truncate text-xs font-medium">{item.value}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


