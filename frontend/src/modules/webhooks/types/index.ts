/**
 * Webhook module types — mirrors backend Pydantic schemas.
 */

export interface Webhook {
    id: string;
    tenant_id: string;
    agent_id: string | null;
    url: string;
    events: string[];
    timeout_seconds: number;
    is_active: boolean;
    secret: string | null;
    created_at: string;
    updated_at: string;
}

export interface WebhookCreateRequest {
    url: string;
    events: string[];
    agent_id?: string | null;
    timeout_seconds?: number;
    secret?: string | null;
}

export interface WebhookUpdateRequest {
    url?: string;
    events?: string[];
    agent_id?: string | null;
    timeout_seconds?: number;
    is_active?: boolean;
    secret?: string | null;
}

export interface WebhookListResponse {
    webhooks: Webhook[];
    total: number;
    page: number;
    limit: number;
}

export interface WebhookDelivery {
    id: string;
    webhook_id: string;
    call_id: string | null;
    event_type: string;
    payload: Record<string, unknown>;
    status: "pending" | "success" | "failed";
    attempts: number;
    last_attempt_at: string | null;
    response_status_code: number | null;
    response_body: string | null;
    error_message: string | null;
    created_at: string;
}

export interface WebhookDeliveryListResponse {
    deliveries: WebhookDelivery[];
    total: number;
    page: number;
    limit: number;
}

export interface WebhookReplayResponse {
    delivery_id: string;
    status: string;
    message: string;
}

export const WEBHOOK_EVENT_TYPES = [
    "call_started",
    "call_ended",
    "call_failed",
    "transcription_complete",
    "extraction_complete",
] as const;

export type WebhookEventType = (typeof WEBHOOK_EVENT_TYPES)[number];
