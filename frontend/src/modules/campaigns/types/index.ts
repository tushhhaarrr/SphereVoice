// Campaign module types — mirrors backend schemas.py exactly

// ─── Enums ───────────────────────────────────────────────────────────────────

export type CampaignStatus =
  | "draft"
  | "loading_contacts"
  | "ready"
  | "scheduled"
  | "running"
  | "paused"
  | "completed"
  | "cancelled"
  | "failed";

export type CampaignContactStatus =
  | "pending"
  | "queued"
  | "calling"
  | "completed"
  | "failed"
  | "no_answer"
  | "busy"
  | "voicemail"
  | "do_not_call"
  | "retry_scheduled"
  | "skipped"
  | "cancelled";

export type WritebackStatus = "pending" | "success" | "failed" | "skipped";

// ─── Campaign ────────────────────────────────────────────────────────────────

export interface CallingWindow {
  start_hour: number;
  end_hour: number;
  timezone: string;
  days_of_week?: number[];
}

export interface CampaignCreate {
  name: string;
  description?: string;
  agent_id: string;
  source_type?: string;
  source_config?: Record<string, unknown>;
  variable_mapping?: Record<string, string>;
  writeback_mapping?: Record<string, string>;
  from_number?: string;
  max_concurrent?: number;
  calls_per_minute?: number;
  max_retries?: number;
  retry_delay_minutes?: number;
  scheduled_at?: string;
  calling_window?: CallingWindow;
  variant_agent_id?: string;
  ab_split_percent?: number;
}

export interface CampaignUpdate {
  name?: string;
  description?: string;
  agent_id?: string;
  source_config?: Record<string, unknown>;
  variable_mapping?: Record<string, string>;
  writeback_mapping?: Record<string, string>;
  from_number?: string;
  max_concurrent?: number;
  calls_per_minute?: number;
  max_retries?: number;
  retry_delay_minutes?: number;
  scheduled_at?: string;
  calling_window?: CallingWindow;
}

export interface Campaign {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  agent_id: string;
  status: CampaignStatus;
  source_type: string;
  source_config: Record<string, unknown>;
  variable_mapping: Record<string, string>;
  writeback_mapping: Record<string, string>;
  from_number: string | null;
  max_concurrent: number;
  calls_per_minute: number;
  max_retries: number;
  retry_delay_minutes: number;
  scheduled_at: string | null;
  calling_window: CallingWindow | null;
  variant_agent_id: string | null;
  ab_split_percent: number;
  total_contacts: number;
  completed_calls: number;
  successful_calls: number;
  failed_calls: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignListItem {
  id: string;
  name: string;
  status: CampaignStatus;
  agent_id: string;
  variant_agent_id: string | null;
  ab_split_percent: number;
  total_contacts: number;
  completed_calls: number;
  scheduled_at: string | null;
  created_at: string;
}

export interface CampaignsListWrapper {
  campaigns: CampaignListItem[];
  total: number;
}

// ─── Campaign Contacts ───────────────────────────────────────────────────────

export interface CampaignContactCreate {
  phone_number: string;
  crm_record_id?: string;
  crm_module?: string;
  contact_data?: Record<string, unknown>;
  priority?: number;
}

export interface CampaignContact {
  id: string;
  tenant_id: string;
  campaign_id: string;
  phone_number: string;
  crm_record_id: string | null;
  crm_module: string | null;
  contact_data: Record<string, unknown>;
  status: CampaignContactStatus;
  call_id: string | null;
  attempt_count: number;
  max_attempts: number;
  next_retry_at: string | null;
  extracted_data: Record<string, unknown>;
  writeback_status: WritebackStatus | null;
  writeback_error: string | null;
  tool_results: Record<string, unknown>[];
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignContactListItem {
  id: string;
  phone_number: string;
  crm_record_id: string | null;
  crm_module: string | null;
  contact_data: Record<string, unknown>;
  status: CampaignContactStatus;
  attempt_count: number;
  call_id: string | null;
  created_at: string;
}

export interface CampaignContactsListWrapper {
  contacts: CampaignContactListItem[];
  total: number;
}

// ─── Stats & Responses ───────────────────────────────────────────────────────

export interface CampaignStats {
  total_contacts: number;
  completed_calls: number;
  successful_calls: number;
  failed_calls: number;
  pending_count: number;
  queued_count: number;
  calling_count: number;
}

export interface LoadContactsRequest {
  contacts: CampaignContactCreate[];
}

export interface LoadContactsResponse {
  loaded: number;
  skipped: number;
}

// ─── Query Params ────────────────────────────────────────────────────────────

export interface CampaignListParams {
  tenant_id?: string;
  status?: CampaignStatus;
  page?: number;
  limit?: number;
}

export interface CampaignContactListParams {
  status?: CampaignContactStatus;
  page?: number;
  limit?: number;
}

// ─── Campaign Builder Wizard ─────────────────────────────────────────────────

export interface CampaignWizardData {
  // Step 1: Agent Select
  agent_id: string;
  // Step 2: CRM Source
  source_type: string;
  source_config: Record<string, unknown>;
  // Step 3: Variable Mapping
  variable_mapping: Record<string, string>;
  // Step 4: Write-Back Mapping
  writeback_mapping: Record<string, string>;
  // Step 5: Call Settings
  name: string;
  description: string;
  from_number: string;
  max_concurrent: number;
  calls_per_minute: number;
  max_retries: number;
  retry_delay_minutes: number;
  scheduled_at: string | null;
  calling_window: CallingWindow | null;
  // Step 6: Tool Config (optional tool overrides)
  tool_config: Record<string, unknown>;
  // A/B testing
  variant_agent_id: string;
  ab_split_percent: number;
}

export const WIZARD_STEPS = [
  { key: "agent", label: "Select Agent" },
  { key: "source", label: "CRM Source" },
  { key: "variables", label: "Variable Mapping" },
  { key: "writeback", label: "Write-Back Mapping" },
  { key: "settings", label: "Call Settings" },
  { key: "ab_test", label: "A/B Test" },
  { key: "tools", label: "Tool Config" },
  { key: "review", label: "Review & Launch" },
] as const;

export type WizardStepKey = (typeof WIZARD_STEPS)[number]["key"];

// ─── Campaign Analytics ──────────────────────────────────────────────────────

export interface ConversionFunnelStage {
  stage: string;
  count: number;
  percent: number;
}

export interface AgentVariantStats {
  agent_id: string;
  label: string;
  total_contacts: number;
  completed: number;
  connection_rate: number;
  avg_duration_seconds: number;
  qualification_rate: number;
  total_cost: number;
}

export interface CampaignAnalytics {
  campaign_id: string;
  total_contacts: number;
  connection_rate: number;
  avg_call_duration_seconds: number;
  extraction_complete_rate: number;
  crm_writeback_success_rate: number;
  cost_per_contact: number;
  total_cost: number;
  status_distribution: Record<string, number>;
  conversion_funnel: ConversionFunnelStage[];
  variant_stats: AgentVariantStats[] | null;
}

// ─── Campaign Templates ─────────────────────────────────────────────────────

export interface CampaignTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  variable_mapping: Record<string, string>;
  writeback_mapping: Record<string, string>;
  call_settings: Record<string, unknown>;
  extraction_hints: string[];
}
