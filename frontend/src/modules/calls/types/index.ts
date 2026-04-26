/**
 * Call module types — aligned with backend CallResponse schema.
 */

export type CallStatus =
  | "queued"
  | "ringing"
  | "in_progress"
  | "completed"
  | "failed"
  | "no_answer";

export type CallDirection = "inbound" | "outbound";

export interface TranscriptEntry {
  speaker: "user" | "agent";
  text: string;
  timestamp: number | string | null;
  confidence: number | null;
}

/** Usage metrics stored as JSONB on the call record. */
export interface UsageMetricsData {
  stt?: { provider?: string | null; model?: string | null; audio_seconds?: number };
  llm?: { provider?: string | null; model?: string | null; input_tokens?: number; output_tokens?: number };
  tts?: { provider?: string | null; model?: string | null; characters?: number };
  telephony?: { provider?: string | null; duration_seconds?: number };
}

/**
 * Matches backend `CallResponse` exactly (tech-prd §6.7).
 */
export interface Call {
  id: string;
  tenant_id: string;
  agent_id: string;
  phone_number_id: string | null;
  from_number: string;
  to_number: string;
  direction: CallDirection;
  status: CallStatus;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  disconnection_reason: string | null;
  recording_url: string | null;
  transcript: TranscriptEntry[] | null;
  extracted_data: Record<string, unknown>;
  extraction_completed_at: string | null;
  avg_latency_ms: number | null;
  turn_count: number;
  stt_cost: string | null;
  llm_cost: string | null;
  tts_cost: string | null;
  telephony_cost: string | null;
  total_cost: string | null; // Decimal serialized as string from backend
  usage_metrics: UsageMetricsData | null;
  created_at: string;
  updated_at: string;
  writeback_status: string | null;
  writeback_error: string | null;
  writeback_completed_at: string | null;
}

export interface CallListResponse {
  calls: Call[];
  total: number;
  page: number;
  limit: number;
}

export interface CallListParams {
  page?: number;
  limit?: number;
  status?: CallStatus;
  direction?: CallDirection;
  agent_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}

export interface OutboundCallRequest {
  agent_id: string;
  to_number: string;
  from_number?: string;
}

export interface OutboundCallResponse {
  call_id: string;
  status: string;
  started_at: string;
}

export type CallExportFormat = "csv" | "json";
