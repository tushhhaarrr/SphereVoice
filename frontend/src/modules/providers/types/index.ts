/**
 * Provider module types.
 */

export type ProviderCategory = "stt" | "llm" | "tts" | "telephony";

export interface Provider {
  id: string;
  tenant_id: string | null;
  provider_name: string;
  provider_family?: string;
  provider_variant?: string | null;
  provider_category: ProviderCategory;
  is_default: boolean;
  is_active: boolean;
  config: Record<string, unknown>;
  test_status: string | null;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderListResponse {
  providers: Provider[];
}

export interface ProviderCreateRequest {
  provider_name: string;
  category: ProviderCategory;
  api_key: string;
  is_default?: boolean;
  tenant_id?: string;
  config?: Record<string, unknown>;
}

export interface ProviderUpdateRequest {
  provider_name?: string;
  api_key?: string;
  is_default?: boolean;
  is_active?: boolean;
  config?: Record<string, unknown>;
}

export interface ProviderTestResponse {
  status: string;
  latency_ms: number | null;
  message: string;
}
