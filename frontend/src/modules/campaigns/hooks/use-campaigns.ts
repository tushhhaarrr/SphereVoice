"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";

/** Parse FastAPI error responses — handles string detail, Pydantic validation arrays, and SphereVoiceException objects. */
function parseApiError(err: unknown, fallback: string): string {
  if (!err || typeof err !== "object") return fallback;
  const obj = err as Record<string, unknown>;
  const detail = obj.detail;
  if (typeof detail === "string") return detail;
  // Pydantic 422: detail is an array of {loc, msg, type}
  if (Array.isArray(detail)) {
    return detail
      .map((e: Record<string, unknown>) => {
        const loc = Array.isArray(e.loc) ? e.loc.slice(1).join(".") : "";
        return loc ? `${loc}: ${e.msg}` : String(e.msg ?? "");
      })
      .join("; ");
  }
  // SphereVoiceException: detail is {error: {code, message, details}}
  if (detail && typeof detail === "object") {
    const inner = (detail as Record<string, unknown>).error;
    if (inner && typeof inner === "object") {
      const msg = (inner as Record<string, unknown>).message;
      if (typeof msg === "string") return msg;
    }
  }
  return fallback;
}

import type {
  Campaign,
  CampaignAnalytics,
  CampaignCreate,
  CampaignUpdate,
  CampaignListParams,
  CampaignsListWrapper,
  CampaignContact,
  CampaignContactListParams,
  CampaignContactsListWrapper,
  CampaignStats,
  CampaignTemplate,
  LoadContactsRequest,
  LoadContactsResponse,
} from "../types";

// ─── Query Keys ──────────────────────────────────────────────────────────────

export const campaignKeys = {
  all: ["campaigns"] as const,
  list: (params?: CampaignListParams) => ["campaigns", "list", params] as const,
  detail: (id: string) => ["campaigns", id] as const,
  stats: (id: string) => ["campaigns", id, "stats"] as const,
  analytics: (id: string) => ["campaigns", id, "analytics"] as const,
  templates: ["campaigns", "templates"] as const,
  contacts: (id: string, params?: CampaignContactListParams) =>
    ["campaigns", id, "contacts", params] as const,
  contact: (campaignId: string, contactId: string) =>
    ["campaigns", campaignId, "contacts", contactId] as const,
};

// ─── Campaign List ───────────────────────────────────────────────────────────

export function useCampaigns(params?: CampaignListParams) {
  const searchParams = new URLSearchParams();
  if (params?.tenant_id) searchParams.set("tenant_id", params.tenant_id);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();

  return useQuery<CampaignsListWrapper>({
    queryKey: campaignKeys.list(params),
    queryFn: async () => {
      try {
        const res = await fetchWithAuth(`/api/v1/campaigns${qs ? `?${qs}` : ""}`);
        if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
        if (!res.ok) return { campaigns: [], total: 0 } as CampaignsListWrapper;
        return res.json();
      } catch (err) {
        if ((err as Error).message === "Unauthorized") throw err;
        return { campaigns: [], total: 0 } as CampaignsListWrapper;
      }
    },
  });
}

// ─── Campaign Detail ─────────────────────────────────────────────────────────

export function useCampaign(id: string, tenantId?: string) {
  const qs = tenantId ? `?tenant_id=${tenantId}` : "";
  return useQuery<Campaign>({
    queryKey: campaignKeys.detail(id),
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/campaigns/${id}${qs}`);
      if (!res.ok) throw new Error("Failed to fetch campaign");
      return res.json();
    },
    enabled: !!id,
  });
}

// ─── Campaign Stats ──────────────────────────────────────────────────────────

export function useCampaignStats(id: string, tenantId?: string) {
  const qs = tenantId ? `?tenant_id=${tenantId}` : "";
  return useQuery<CampaignStats>({
    queryKey: campaignKeys.stats(id),
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/campaigns/${id}/stats${qs}`);
      if (!res.ok) throw new Error("Failed to fetch campaign stats");
      return res.json();
    },
    enabled: !!id,
    refetchInterval: 5000, // Poll every 5s for live dashboard
  });
}

// ─── Campaign Contacts ───────────────────────────────────────────────────────

export function useCampaignContacts(
  campaignId: string,
  params?: CampaignContactListParams,
  tenantId?: string
) {
  const searchParams = new URLSearchParams();
  if (tenantId) searchParams.set("tenant_id", tenantId);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();

  return useQuery<CampaignContactsListWrapper>({
    queryKey: campaignKeys.contacts(campaignId, params),
    queryFn: async () => {
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/contacts${qs ? `?${qs}` : ""}`
      );
      if (!res.ok) throw new Error("Failed to fetch campaign contacts");
      return res.json();
    },
    enabled: !!campaignId,
  });
}

// ─── Single Contact Detail ───────────────────────────────────────────────────

export function useCampaignContact(campaignId: string, contactId: string, tenantId?: string) {
  const qs = tenantId ? `?tenant_id=${tenantId}` : "";
  return useQuery<CampaignContact>({
    queryKey: campaignKeys.contact(campaignId, contactId),
    queryFn: async () => {
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/contacts/${contactId}${qs}`
      );
      if (!res.ok) throw new Error("Failed to fetch contact detail");
      return res.json();
    },
    enabled: !!campaignId && !!contactId,
  });
}

// ─── Create Campaign ─────────────────────────────────────────────────────────

export function useCreateCampaign(tenantId?: string) {
  const queryClient = useQueryClient();
  const qs = tenantId ? `?tenant_id=${tenantId}` : "";

  return useMutation<Campaign, Error, CampaignCreate>({
    mutationFn: async (data) => {
      const res = await fetchWithAuth(`/api/v1/campaigns${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to create campaign"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignKeys.all });
    },
  });
}

// ─── Update Campaign ─────────────────────────────────────────────────────────

export function useUpdateCampaign(id: string, tenantId?: string) {
  const queryClient = useQueryClient();
  const qs = tenantId ? `?tenant_id=${tenantId}` : "";

  return useMutation<Campaign, Error, CampaignUpdate>({
    mutationFn: async (data) => {
      const res = await fetchWithAuth(`/api/v1/campaigns/${id}${qs}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to update campaign"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: campaignKeys.all });
    },
  });
}

// ─── Delete Campaign ─────────────────────────────────────────────────────────

export function useDeleteCampaign() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { id: string; tenantId?: string }>({
    mutationFn: async ({ id, tenantId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(`/api/v1/campaigns/${id}${qs}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to delete campaign"));
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignKeys.all });
    },
  });
}

// ─── Load Contacts ───────────────────────────────────────────────────────────

export function useLoadContacts(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<LoadContactsResponse, Error, LoadContactsRequest>({
    mutationFn: async (data) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/load-contacts${qs}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to load contacts"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: campaignKeys.detail(campaignId),
      });
      queryClient.invalidateQueries({
        queryKey: campaignKeys.contacts(campaignId),
      });
    },
  });
}

// ─── Campaign Actions (Start / Pause / Resume / Cancel) ──────────────────────

function useCampaignAction(action: "start" | "pause" | "resume" | "cancel") {
  const queryClient = useQueryClient();

  return useMutation<Campaign, Error, { id: string; tenantId?: string }>({
    mutationFn: async ({ id, tenantId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(`/api/v1/campaigns/${id}/${action}${qs}`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, `Failed to ${action} campaign`));
      }
      return res.json();
    },
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: campaignKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: campaignKeys.stats(id) });
      queryClient.invalidateQueries({ queryKey: campaignKeys.all });
    },
  });
}

export function useStartCampaign() {
  return useCampaignAction("start");
}

export function usePauseCampaign() {
  return useCampaignAction("pause");
}

export function useResumeCampaign() {
  return useCampaignAction("resume");
}

export function useCancelCampaign() {
  return useCampaignAction("cancel");
}

// ─── Retry Contact ───────────────────────────────────────────────────────────

export function useRetryContact(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<CampaignContact, Error, string>({
    mutationFn: async (contactId) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/contacts/${contactId}/retry${qs}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to retry contact"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: campaignKeys.contacts(campaignId),
      });
      queryClient.invalidateQueries({
        queryKey: campaignKeys.stats(campaignId),
      });
    },
  });
}

// ─── Export Results ───────────────────────────────────────────────────────────

export function useExportResults() {
  return useMutation<Blob, Error, { campaignId: string; tenantId?: string }>({
    mutationFn: async ({ campaignId, tenantId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/export${qs}`
      );
      if (!res.ok) throw new Error("Failed to export campaign results");
      return res.blob();
    },
  });
}

// ─── Load Contacts from CRM ─────────────────────────────────────────────────

export function useLoadContactsFromCrm(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<LoadContactsResponse, Error, void>({
    mutationFn: async () => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/load-from-crm${qs}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to load contacts from CRM"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: campaignKeys.detail(campaignId),
      });
      queryClient.invalidateQueries({
        queryKey: campaignKeys.contacts(campaignId),
      });
    },
  });
}

// ─── Agent Prompt Variables ──────────────────────────────────────────────────

export interface DefinedVariable {
  name: string;
  description?: string;
  default_value?: string;
}

export interface AgentPromptVariables {
  agent_id: string;
  agent_name: string;
  prompt_variables: string[];
  vars_by_source: Record<string, string[]>;
  defined_variables: DefinedVariable[];
  extraction_fields: Record<string, unknown>[];
  prompt_preview: string;
}

export function useAgentPromptVariables(agentId: string) {
  return useQuery<AgentPromptVariables>({
    queryKey: ["agents", agentId, "prompt-variables"],
    queryFn: async () => {
      const res = await fetchWithAuth(
        `/api/v1/agents/${agentId}/prompt-variables`
      );
      if (!res.ok) throw new Error("Failed to fetch agent prompt variables");
      return res.json();
    },
    enabled: !!agentId,
  });
}

// ─── CRM Module Fields ──────────────────────────────────────────────────────

export interface CrmField {
  api_name: string;
  display_label: string;
  data_type: string;
  read_only: boolean;
  required: boolean;
}

export interface CrmModuleFieldsResponse {
  module: string;
  fields: CrmField[];
}

export function useCrmModuleFields(module: string, tenantId?: string) {
  return useQuery<CrmModuleFieldsResponse>({
    queryKey: ["crm-module-fields", module, tenantId],
    queryFn: async () => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      try {
        const res = await fetchWithAuth(`/api/v1/integrations/crm/modules/${module}/fields${qs}`);
        if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
        if (!res.ok) return { module, fields: [] } as CrmModuleFieldsResponse;
        return res.json();
      } catch (err) {
        if ((err as Error).message === "Unauthorized") throw err;
        return { module, fields: [] } as CrmModuleFieldsResponse;
      }
    },
    enabled: !!module,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
}

// ─── AI CRM Mapping Suggestion ──────────────────────────────────────────────

export interface AiCrmMappingRequest {
  source_fields: { name: string; description?: string }[];
  crm_fields: { api_name: string; display_label: string; data_type: string }[];
  direction: "read" | "write";
}

export function useAiCrmMapping() {
  return useMutation<{ mappings: Record<string, string> }, Error, AiCrmMappingRequest>({
    mutationFn: async (body) => {
      const res = await fetchWithAuth("/api/v1/agents/ai/suggest-crm-mapping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("AI mapping suggestion failed");
      return res.json();
    },
  });
}

// ─── CRM Module Views ───────────────────────────────────────────────────────

export interface CrmView {
  id: string;
  name: string;
  system_name: string;
  default: boolean;
}

export interface CrmModuleViewsResponse {
  module: string;
  views: CrmView[];
}

export function useCrmModuleViews(module: string, tenantId?: string) {
  return useQuery<CrmModuleViewsResponse>({
    queryKey: ["crm-module-views", module, tenantId],
    queryFn: async () => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      try {
        const res = await fetchWithAuth(`/api/v1/integrations/crm/modules/${module}/views${qs}`);
        if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
        if (!res.ok) return { module, views: [] } as CrmModuleViewsResponse;
        return res.json();
      } catch (err) {
        if ((err as Error).message === "Unauthorized") throw err;
        return { module, views: [] } as CrmModuleViewsResponse;
      }
    },
    enabled: !!module,
    staleTime: 5 * 60 * 1000,
  });
}

// ─── CSV Upload ──────────────────────────────────────────────────────────────

export interface CsvUploadResponse {
  columns: string[];
  row_count: number;
  sample_rows: Record<string, string>[];
}

export function useUploadCsv(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<CsvUploadResponse, Error, File>({
    mutationFn: async (file) => {
      const formData = new FormData();
      formData.append("file", file);
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/upload-csv${qs}`,
        { method: "POST", body: formData }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to upload CSV"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: campaignKeys.detail(campaignId),
      });
    },
  });
}

// ─── CSV Load ────────────────────────────────────────────────────────────────

export interface CsvLoadRequest {
  column_mapping: Record<string, string>;
}

export interface CsvLoadResponse {
  loaded: number;
  skipped: number;
  invalid_rows: { row_index: number; reason: string }[];
}

export function useLoadFromCsv(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<CsvLoadResponse, Error, CsvLoadRequest>({
    mutationFn: async (body) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/load-from-csv${qs}`,
        { method: "POST", body: JSON.stringify(body) }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to load CSV contacts"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: campaignKeys.detail(campaignId),
      });
      queryClient.invalidateQueries({
        queryKey: campaignKeys.contacts(campaignId),
      });
      queryClient.invalidateQueries({
        queryKey: campaignKeys.stats(campaignId),
      });
    },
  });
}

// ─── Contact Preview ─────────────────────────────────────────────────────────

export interface ContactPreview {
  name: string;
  phone: string;
  email: string;
  company: string;
  crm_id: string;
}

export interface ContactPreviewResponse {
  total: number;
  contacts: ContactPreview[];
}

export function usePreviewContacts(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<ContactPreviewResponse, Error, void>({
    mutationFn: async () => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/preview-contacts${qs}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to preview contacts"));
      }
      return res.json();
    },
  });
}

// ─── Campaign Clone ──────────────────────────────────────────────────────────

export interface CampaignCloneResponse {
  id: string;
  name: string;
  status: string;
}

export function useCloneCampaign() {
  const queryClient = useQueryClient();

  return useMutation<CampaignCloneResponse, Error, { campaignId: string; tenantId?: string }>({
    mutationFn: async ({ campaignId, tenantId }) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/clone${qs}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to clone campaign"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: campaignKeys.all });
    },
  });
}

// ─── Retry All Failed ────────────────────────────────────────────────────────

export interface RetryAllFailedResponse {
  retried: number;
}

export function useRetryAllFailed(campaignId: string, tenantId?: string) {
  const queryClient = useQueryClient();

  return useMutation<RetryAllFailedResponse, Error, void>({
    mutationFn: async () => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/retry-failed${qs}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Failed to retry failed contacts"));
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: campaignKeys.contacts(campaignId),
      });
      queryClient.invalidateQueries({
        queryKey: campaignKeys.stats(campaignId),
      });
    },
  });
}

// ─── Campaign Analytics ──────────────────────────────────────────────────────

export function useCampaignAnalytics(campaignId: string, tenantId?: string) {
  const qs = tenantId ? `?tenant_id=${tenantId}` : "";
  return useQuery<CampaignAnalytics>({
    queryKey: campaignKeys.analytics(campaignId),
    queryFn: async () => {
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/analytics${qs}`
      );
      if (!res.ok) throw new Error("Failed to fetch campaign analytics");
      return res.json();
    },
    enabled: !!campaignId,
  });
}

// ─── Campaign Templates ─────────────────────────────────────────────────────

export function useCampaignTemplates() {
  return useQuery<CampaignTemplate[]>({
    queryKey: campaignKeys.templates,
    queryFn: async () => {
      const res = await fetchWithAuth("/api/v1/campaigns/templates/list");
      if (!res.ok) throw new Error("Failed to fetch campaign templates");
      return res.json();
    },
  });
}

// ─── Campaign Dry Run ────────────────────────────────────────────────────────

export interface DryRunContactResult {
  phone_number: string;
  contact_data: Record<string, unknown>;
  resolved_variables: Record<string, string>;
  rendered_prompt: string;
  simulated_transcript: { role: string; content: string }[];
  extracted_data: Record<string, unknown>;
  writeback_preview: Record<string, unknown>;
}

export interface DryRunResponse {
  campaign_id: string;
  agent_name: string;
  results: DryRunContactResult[];
  warnings: string[];
}

export function useDryRun(campaignId: string, tenantId?: string) {
  return useMutation<DryRunResponse, Error, number>({
    mutationFn: async (count = 1) => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/campaigns/${campaignId}/dry-run${qs}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ count }),
        }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Dry run failed"));
      }
      return res.json();
    },
  });
}
