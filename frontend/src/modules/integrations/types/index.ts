export interface CrmIntegration {
  id: string;
  tenant_id: string;
  provider: string;
  status: "connected" | "error" | "disconnected";
  data_center: string;
  org_id: string | null;
  org_name: string | null;
  config: Record<string, unknown>;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CrmIntegrationListResponse {
  integrations: CrmIntegration[];
  total: number;
}

export interface ZohoInitiateResponse {
  auth_url: string;
}

/** Generic OAuth initiate response — same shape for all CRM providers. */
export type OAuthInitiateResponse = ZohoInitiateResponse;

export interface ZohoSyncResponse {
  status: string;
  message: string;
  org_id: string | null;
  org_name: string | null;
}

export type ZohoDataCenter = "com" | "eu" | "in" | "au" | "jp" | "ca" | "uk";

export const ZOHO_DATA_CENTER_LABELS: Record<ZohoDataCenter, string> = {
  com: "Global (zoho.com)",
  eu: "Europe (zoho.eu)",
  in: "India (zoho.in)",
  au: "Australia (zoho.com.au)",
  jp: "Japan (zoho.jp)",
  ca: "Canada (zohocloud.ca)",
  uk: "United Kingdom (zoho.uk)",
};

// ── CRM Data types ──────────────────────────────────────────

export interface ZohoRecord {
  id: string;
  Full_Name?: string | null;
  First_Name?: string | null;
  Last_Name?: string | null;
  Email?: string | null;
  Phone?: string | null;
  Mobile?: string | null;
  Company?: string | null;
  Title?: string | null;
  Owner?: { name?: string; id?: string } | null;
  Created_Time?: string | null;
  Modified_Time?: string | null;
  // Lead-specific
  Lead_Status?: string | null;
  Lead_Source?: string | null;
  // Deal-specific
  Deal_Name?: string | null;
  Stage?: string | null;
  Amount?: number | null;
  Closing_Date?: string | null;
  // Account-specific
  Account_Name?: string | null;
  Industry?: string | null;
  Annual_Revenue?: number | null;
  Account_Type?: string | null;
  Number_of_Employees?: number | null;
  Website?: string | null;
  // Task-specific
  Subject?: string | null;
  Status?: string | null;
  Priority?: string | null;
  Due_Date?: string | null;
  Description?: string | null;
  // Call-specific
  Call_Type?: string | null;
  Call_Start_Time?: string | null;
  Call_Duration?: string | null;
  Call_Purpose?: string | null;
  Call_Result?: string | null;
  // Note-specific
  Note_Title?: string | null;
  Note_Content?: string | null;
  se_module?: string | null;
  // Meeting/Event-specific
  Event_Title?: string | null;
  Start_DateTime?: string | null;
  End_DateTime?: string | null;
  Location?: string | null;
  // Campaign-specific
  Campaign_Name?: string | null;
  Type?: string | null;
  Start_Date?: string | null;
  End_Date?: string | null;
  Expected_Revenue?: number | null;
  Actual_Cost?: number | null;
  // Location
  Mailing_City?: string | null;
  Mailing_State?: string | null;
  Mailing_Country?: string | null;
  [key: string]: unknown;
}

export interface ZohoRecordListResponse {
  data: ZohoRecord[];
  info: {
    per_page?: number;
    count?: number;
    page?: number;
    more_records?: boolean;
  };
}

export interface ZohoCallerEnrichmentResponse {
  found: boolean;
  module?: string | null;
  record?: ZohoRecord | null;
}

export interface CrmCallFromCrmRequest {
  contact_id: string;
  contact_module?: string;
  phone_field?: string;
  agent_id: string;
}

export interface CrmCallFromCrmResponse {
  call_id: string;
  to_number: string;
  contact_name: string;
  crm_contact_id: string;
  status: string;
}

// ── CRM Settings types ──────────────────────────────────────

export interface CrmSettingsResponse {
  default_country: string;
  auto_create_contact: boolean;
  field_mappings: Record<string, string>;
}

export interface CrmSettingsUpdateRequest {
  default_country?: string;
  auto_create_contact?: boolean;
  field_mappings?: Record<string, string>;
}

export const SUPPORTED_COUNTRIES: Record<string, string> = {
  IN: "India (+91)",
  US: "United States (+1)",
};

/** Default SphereVoice extraction fields available for mapping to Zoho CRM fields. */
export const SphereVoice_EXTRACTABLE_FIELDS = [
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "email", label: "Email" },
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "date_of_birth", label: "Date of Birth" },
  { key: "insurance_provider", label: "Insurance Provider" },
  { key: "mailing_address", label: "Mailing Address" },
  { key: "city", label: "City" },
  { key: "state", label: "State" },
  { key: "zip_code", label: "Zip Code" },
  { key: "country", label: "Country" },
] as const;

/** Common Zoho CRM Contact fields that can be mapped to. */
export const ZOHO_CONTACT_FIELDS = [
  "First_Name",
  "Last_Name",
  "Email",
  "Phone",
  "Mobile",
  "Company",
  "Title",
  "Date_of_Birth",
  "Department",
  "Description",
  "Mailing_Street",
  "Mailing_City",
  "Mailing_State",
  "Mailing_Zip",
  "Mailing_Country",
  "Other_Street",
  "Other_City",
  "Other_State",
  "Other_Zip",
  "Other_Country",
  "Lead_Source",
  "Fax",
  "Secondary_Email",
] as const;

// ── Tenant Integration types ─────────────────────────────────

export type IntegrationCategory = "crm" | "calendar" | "messaging" | "email" | "custom_webhook";
export type IntegrationStatus = "active" | "inactive" | "error";

export interface CategoryMeta {
  key: IntegrationCategory;
  label: string;
  description: string;
  providers: { value: string; label: string; description: string }[];
}

export interface TenantIntegration {
  id: string;
  tenant_id: string;
  name: string;
  category: IntegrationCategory;
  provider: string;
  status: IntegrationStatus;
  config: Record<string, unknown> | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantIntegrationListResponse {
  integrations: TenantIntegration[];
  total: number;
}

export interface TenantIntegrationCreate {
  name: string;
  category: IntegrationCategory;
  provider: string;
  status?: IntegrationStatus;
  credentials?: Record<string, unknown>;
  config?: Record<string, unknown>;
}

export interface TenantIntegrationUpdate {
  name?: string;
  status?: IntegrationStatus;
  credentials?: Record<string, unknown>;
  config?: Record<string, unknown>;
}

// ── CRM Cache / Sync types ─────────────────────────────────

export interface CachedContact {
  id: string;
  crm_record_id: string;
  crm_module: "Contacts" | "Leads";
  full_name: string | null;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  company: string | null;
  title: string | null;
  lead_status: string | null;
  lead_source: string | null;
  mailing_city: string | null;
  mailing_state: string | null;
  mailing_country: string | null;
  owner_name: string | null;
  synced_at: string | null;
}

export interface CachedContactListResponse {
  data: CachedContact[];
  info: {
    per_page?: number;
    count?: number;
    page?: number;
    more_records?: boolean;
    total?: number;
  };
}

export interface SyncStatusResponse {
  total_cached: number;
  contacts_cached: number;
  leads_cached: number;
  last_full_sync_at: string | null;
  last_incremental_sync_at: string | null;
  last_synced_at: string | null;
  sync_in_progress: boolean;
}

export interface SyncTriggerResponse {
  status: string;
  message: string;
}

// ── Google Integration types ─────────────────────────────────

export interface GoogleIntegration {
  id: string;
  tenant_id: string;
  provider: "google_calendar" | "google_sheets";
  status: "connected" | "error" | "disconnected";
  account_email: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoogleIntegrationListResponse {
  integrations: GoogleIntegration[];
  total: number;
}

export interface GoogleInitiateResponse {
  auth_url: string;
}

export interface GoogleSyncResponse {
  status: string;
  message: string;
  account_email: string | null;
}

// ── Calendly Integration types ───────────────────────────────

export interface CalendlyIntegration {
  id: string;
  tenant_id: string;
  provider: "calendly";
  status: "connected" | "error" | "disconnected";
  account_email: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendlyIntegrationListResponse {
  integrations: CalendlyIntegration[];
  total: number;
}

export interface CalendlyInitiateResponse {
  auth_url: string;
}

export interface CalendlySyncResponse {
  status: string;
  message: string;
  account_email: string | null;
}
