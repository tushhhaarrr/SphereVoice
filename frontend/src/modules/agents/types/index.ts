/**
 * Agent module types.
 */

export type AgentType = "conversation_flow" | "single_prompt";

export type AgentStatus = "draft" | "published" | "archived";

export type CallDirection = "inbound" | "outbound";

export interface Agent {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  type: AgentType;
  status: AgentStatus;
  call_direction: CallDirection;
  stt_provider_id: string | null;
  llm_provider_id: string | null;
  tts_provider_id: string | null;
  telephony_provider_id: string | null;
  config: Record<string, unknown>;
  language: string;
  voice_id: string | null;
  voice_speed: number;
  voice_volume: number;
  llm_model: string | null;
  llm_temperature: number;
  llm_max_tokens: number;
  max_call_duration_seconds: number;
  end_on_silence_seconds: number;
  ring_duration_seconds: number;
  voicemail_detection: string;
  extraction_fields: Record<string, unknown>[];
  webhook_url: string | null;
  webhook_events: string[];
  version: number;
  published_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentListResponse {
  // Backend field names
  nodes?: Agent[];
  total_count?: number;
  cursor_position?: number;
  limit_bound?: number;
  // Fallback/alias fields used by some frontend components
  agents?: Agent[];
  total?: number;
  page?: number;
  limit?: number;
}

export interface AgentCreateRequest {
  tenant_id: string;
  name: string;
  type: AgentType;
  call_direction?: CallDirection;
  config?: Record<string, unknown>;
  language?: string;
  stt_provider_id?: string | null;
  llm_provider_id?: string | null;
  tts_provider_id?: string | null;
  telephony_provider_id?: string | null;
  voice_id?: string | null;
  voice_speed?: number;
  voice_volume?: number;
  llm_model?: string | null;
  llm_temperature?: number;
  llm_max_tokens?: number;
  max_call_duration_seconds?: number;
  end_on_silence_seconds?: number;
  ring_duration_seconds?: number;
  voicemail_detection?: string;
  extraction_fields?: Record<string, unknown>[];
  webhook_url?: string | null;
  webhook_events?: string[];
}

export interface AgentVersion {
  id: string;
  version: number;
  published_at: string;
  published_by: string | null;
}

// ── Test Scenarios ──────────────────────────────────────────

export interface TestScenario {
  id: string;
  agent_id: string;
  name: string;
  description: string | null;
  dynamic_variables: Record<string, unknown>;
  expected_outcomes: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestScenarioListResponse {
  scenarios: TestScenario[];
  total: number;
}

export interface TestScenarioCreate {
  name: string;
  description?: string;
  dynamic_variables: Record<string, unknown>;
  expected_outcomes: Record<string, unknown>;
}

export interface TestScenarioUpdate {
  name?: string;
  description?: string;
  dynamic_variables?: Record<string, unknown>;
  expected_outcomes?: Record<string, unknown>;
}

export interface MatchField {
  field: string;
  expected: unknown;
  actual: unknown;
  match: boolean;
  strategy: string;
}

export interface TestCallResult {
  id: string;
  scenario_id: string;
  call_id: string | null;
  agent_version: number | null;
  extracted_data: Record<string, unknown>;
  expected_outcomes: Record<string, unknown>;
  match_results: {
    fields: MatchField[];
    total: number;
    matched: number;
    passed: boolean;
  };
  passed: boolean;
  total_fields: number;
  matched_fields: number;
  created_at: string;
}

export interface TestCallResultListResponse {
  results: TestCallResult[];
  total: number;
}

export interface RunScenarioRequest {
  agent_version?: number | null;
}
