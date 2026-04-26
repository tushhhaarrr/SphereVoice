/**
 * Live monitoring module types.
 */

export type LiveCallStatus =
  | "active"
  | "ringing"
  | "on_hold"
  | "transferring"
  | "ending";

export interface TranscriptEntry {
  speaker: "user" | "assistant";
  text: string;
  timestamp: string;
  confidence?: number;
}

export interface CallMetrics {
  latencyMs: number;
  turnCount: number;
  functionCalls: number;
}

export interface LiveCall {
  callId: string;
  tenantId?: string;
  agentId: string;
  agentName: string;
  callerNumber: string;
  calledNumber: string;
  direction: "inbound" | "outbound";
  duration: number;
  status: LiveCallStatus;
  startedAt: string;
  sentiment: "positive" | "neutral" | "negative" | null;
  lastTranscript: string | null;
  transcript: TranscriptEntry[];
  metrics: CallMetrics;
}

export interface LiveMetrics {
  activeCalls: number;
  totalCallsToday: number;
  avgDuration: number;
  avgLatencyMs: number;
}

export type LiveEventType =
  | "call_started"
  | "call_updated"
  | "call_ended"
  | "transcript_update"
  | "metrics_update"
  | "subscribed"
  | "ping";

export interface LiveEvent {
  event: LiveEventType;
  data: Record<string, unknown>;
}

export type WebSocketStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";
