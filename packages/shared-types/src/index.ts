/**
 * @SphereVoice/shared-types — Shared TypeScript types for the SphereVoice platform.
 *
 * Used by frontend and any other TypeScript packages in the monorepo.
 */

// ── Provider Types ─────────────────────────────────────────
export type ProviderCategory = "stt" | "llm" | "tts" | "telephony";

export type STTProvider = "deepgram" | "assemblyai" | "azure_speech" | "openai_whisper";
export type LLMProvider = "openai" | "anthropic" | "groq" | "azure_openai";
export type TTSProvider = "cartesia" | "elevenlabs" | "openai_tts" | "lmnt" | "playht" | "azure_speech";
export type TelephonyProvider = "plivo" | "twilio" | "vobiz" | "vonage" | "telnyx";

// ── Agent Types ────────────────────────────────────────────
export type AgentType = "conversation_flow" | "single_prompt";
export type AgentStatus = "draft" | "published" | "archived";
export type ExecutionMode = "flex" | "rigid";

// ── Call Types ─────────────────────────────────────────────
export type CallStatus = "queued" | "ringing" | "in_progress" | "completed" | "failed" | "no_answer";
export type CallDirection = "inbound" | "outbound";

// ── User / Auth Types ──────────────────────────────────────
export type UserRole = "admin" | "developer" | "read_only" | "client";

// ── Flow Node Types ────────────────────────────────────────
export type NodeType =
  | "conversation"
  | "function"
  | "logic_split"
  | "call_transfer"
  | "press_digit"
  | "extract_variable"
  | "sms"
  | "ending";

// ── API Response Types ─────────────────────────────────────
export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
