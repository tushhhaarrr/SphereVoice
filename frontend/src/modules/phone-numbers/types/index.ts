/**
 * Phone Numbers module — TypeScript types.
 */

export type PhoneNumberStatus = "active" | "inactive";

export interface PhoneNumberCapabilities {
  voice: boolean;
  sms: boolean;
  mms: boolean;
}

export interface PhoneNumber {
  id: string;
  tenant_id: string;
  phone_number: string;
  country_code: string | null;
  provider_name: string;
  provider_sid: string | null;
  agent_id: string | null;
  fallback_number: string | null;
  webhook_url: string | null;
  capabilities: PhoneNumberCapabilities;
  monthly_cost: number | null;
  is_default_outbound: boolean;
  status: PhoneNumberStatus;
  purchased_at: string;
  created_at: string;
  /** Resolved tenant name (populated by list endpoint) */
  tenant_name?: string | null;
  /** Resolved agent name (populated by list endpoint) */
  agent_name?: string | null;
}

export interface AvailableNumber {
  phone_number: string;
  country_code: string;
  capabilities: PhoneNumberCapabilities;
  monthly_cost: number;
  /** Which provider this number was found through */
  provider: string;
}

export interface PhoneNumberListResponse {
  numbers: PhoneNumber[];
  total: number;
  page: number;
  limit: number;
}

export interface PhoneNumberSearchResponse {
  numbers: AvailableNumber[];
}

export interface PhoneNumberListParams {
  page?: number;
  limit?: number;
  status?: PhoneNumberStatus;
  agent_id?: string;
  tenant_id?: string;
}

export interface PhoneNumberSearchParams {
  country?: string;
  area_code?: string;
  contains?: string;
  limit?: number;
  provider?: string;
}

export interface PhoneNumberPurchaseRequest {
  phone_number: string;
  tenant_id?: string;
  provider_name?: string;
}

export interface PhoneNumberAssignRequest {
  agent_id: string | null;
}
