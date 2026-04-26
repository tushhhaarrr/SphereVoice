/**
 * Analytics module types.
 */

// ── Metric Cards ────────────────────────────────────────────

export interface TrendIndicator {
  value: number;
  direction: "up" | "down" | "flat";
}

export interface MetricCardsResponse {
  total_calls: number;
  completed_calls: number;
  failed_calls: number;
  avg_duration_seconds: number;
  total_duration_seconds: number;
  avg_latency_p50_ms: number;
  avg_latency_p99_ms: number;
  success_rate: number;
  active_calls: number;
  trend_calls: TrendIndicator;
  trend_duration: TrendIndicator;
  trend_latency: TrendIndicator;
  trend_success_rate: TrendIndicator;
}

// ── Time Series ─────────────────────────────────────────────

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface TimeSeriesResponse {
  metric: string;
  granularity: string;
  data: TimeSeriesPoint[];
}

export type TimeSeriesMetric =
  | "call_count"
  | "avg_duration"
  | "avg_latency"
  | "success_rate"
  | "total_duration";

export type Granularity = "day" | "week" | "month";

// ── Extraction Metrics ──────────────────────────────────────

export interface ExtractionMetricsResponse {
    extraction_success_rate: number;
    avg_success_score: number;
    sentiment_distribution: Record<string, number>;
    frustration_rate: number;
    calls_with_extraction: number;
    total_calls_in_period: number;
    trend_success_rate: TrendIndicator | null;
    trend_frustration_rate: TrendIndicator | null;
}

// ── Audit Logs ──────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  user_email: string | null;
  tenant_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  changes: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  timestamp: string;
}

export interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  limit: number;
}

// ── Templates ───────────────────────────────────────────────

export type TemplateScope = "private" | "tenant" | "global";

export interface AgentTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string;
  tags: string[];
  is_builtin: boolean;
  scope: TemplateScope;
  agent_type: string;
  config: Record<string, unknown>;
  voice_id: string | null;
  language: string;
  llm_model: string | null;
  llm_temperature: number;
  extraction_fields: Record<string, unknown>[];
  kb_suggestions: string[];
  version: number;
  created_by: string | null;
  tenant_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  templates: AgentTemplate[];
  total: number;
}

export interface TemplateCreateRequest {
  name: string;
  description?: string;
  category: string;
  tags?: string[];
  scope?: TemplateScope;
  agent_type: string;
  config: Record<string, unknown>;
  voice_id?: string;
  language?: string;
  llm_model?: string;
  llm_temperature?: number;
  extraction_fields?: Record<string, unknown>[];
  kb_suggestions?: string[];
}

export interface TemplateCreateAgentRequest {
  tenant_id: string;
  name: string;
}

// ── User Management ─────────────────────────────────────────

export type UserRole = "admin" | "developer" | "read_only" | "client_user";

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  tenant_id: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  users: UserProfile[];
  total: number;
  page: number;
  limit: number;
}

export interface UserInviteRequest {
  email: string;
  name?: string;
  role: UserRole;
  tenant_id?: string;
}

export interface UserInviteSentResponse {
  message: string;
  email: string;
  role: string;
  expires_in_hours: number;
  /** Only present in dev mode (EMAIL_ENABLED=false) */
  invite_link: string | null;
}

export interface UserUpdateRequest {
  name?: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface InvitationRecord {
  id: string;
  email: string;
  name: string | null;
  role: string;
  tenant_id: string | null;
  expires_at: string;
  created_at: string;
  is_expired: boolean;
}

export interface InvitationListResponse {
  invitations: InvitationRecord[];
  total: number;
}

// ── Tenant Management ─────────────────────────────────────

export type TenantStatus = "active" | "inactive" | "suspended";

export interface TenantSummary {
  user_count: number;
  agent_count: number;
  call_count: number;
  phone_number_count: number;
}

export interface TenantRecord {
  id: string;
  name: string;
  slug: string;
  status: TenantStatus;
  metadata: Record<string, unknown>;
  summary: TenantSummary;
  created_at: string;
  updated_at: string;
}

export interface TenantListResponse {
  tenants: TenantRecord[];
  total: number;
  page: number;
  limit: number;
}

export interface TenantCreateRequest {
  name: string;
  slug?: string;
  status?: TenantStatus;
  metadata?: Record<string, unknown>;
  website_url?: string;
}

export interface TenantUpdateRequest {
  name?: string;
  slug?: string;
  status?: TenantStatus;
  metadata?: Record<string, unknown>;
}
