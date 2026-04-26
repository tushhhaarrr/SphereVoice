"use client";

/**
 * Hook to fetch real CRM fields and convert them into PromptVariable[]
 * for the prompt editor autocomplete / variable picker.
 *
 * When a tenant has a CRM connected, the prompt editor shows actual CRM field
 * names (e.g. Full_Name, Company, Email) instead of generic placeholders.
 * This makes campaign variable mapping trivial — variable names match CRM
 * field API names so everything auto-maps.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";
import type { PromptVariable } from "../components/prompt-editor";

interface CrmField {
  api_name: string;
  display_label: string;
  data_type: string;
  read_only: boolean;
  required: boolean;
}

interface CrmModuleFieldsResponse {
  module: string;
  fields: CrmField[];
}

interface CrmIntegration {
  id: string;
  provider: string;
  status: string;
}

interface CrmIntegrationListResponse {
  integrations: CrmIntegration[];
}

/** Lightweight check — is any CRM connected for this tenant? */
function useCrmConnected(tenantId?: string) {
  return useQuery<CrmIntegrationListResponse>({
    queryKey: ["integrations", "crm", tenantId, "connected-check"],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tenantId) params.set("tenant_id", tenantId);
      const qs = params.toString();
      const res = await fetchWithAuth(`/api/v1/integrations/crm${qs ? `?${qs}` : ""}`);
      if (!res.ok) throw new Error("Failed to fetch CRM integrations");
      return res.json();
    },
    enabled: !!tenantId,
    staleTime: 5 * 60_000,
  });
}

/** Fields that are noise in the prompt editor — internal IDs, system audit fields, etc. */
const EXCLUDED_FIELDS = new Set([
  "id",
  "Created_By",
  "Modified_By",
  "Created_Time",
  "Modified_Time",
  "Last_Activity_Time",
  "Tag",
  "Locked__s",
  "Record_Image",
  "$currency_symbol",
  "$converted",
  "$approved",
  "$approval_state",
  "$in_merge",
  "$converted_detail",
  "$review",
  "$review_process",
  "$orchestration",
  "$followers",
  "Exchange_Rate",
  "Currency",
  "Layout",
]);

/** CRM data types that are useful as prompt variables (text-representable) */
const USEFUL_DATA_TYPES = new Set([
  "text",
  "textarea",
  "email",
  "phone",
  "website",
  "picklist",
  "multipicklist",
  "date",
  "datetime",
  "integer",
  "bigint",
  "double",
  "currency",
  "boolean",
  "lookup",
  "autonumber",
  "formula",
]);

/**
 * Fetch real CRM fields for a tenant and convert them to PromptVariable objects.
 *
 * @param tenantId - The tenant to fetch CRM fields for
 * @param crmModule - CRM module to pull fields from (default: "Leads")
 * @returns { variables, isLoading, isCrmConnected }
 */
export function useCrmFieldVariables(
  tenantId?: string,
  crmModule = "Leads",
) {
  const { data: crmData, isLoading: checkingCrm } = useCrmConnected(tenantId);
  const isCrmConnected = crmData?.integrations?.some(
    (i) => i.status === "connected",
  ) ?? false;

  const { data: fieldsData, isLoading: loadingFields } = useQuery<CrmModuleFieldsResponse>({
    queryKey: ["crm-module-fields", crmModule, tenantId, "prompt-variables"],
    queryFn: async () => {
      const qs = tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await fetchWithAuth(
        `/api/v1/integrations/crm/modules/${crmModule}/fields${qs}`,
      );
      if (!res.ok) throw new Error("Failed to fetch CRM module fields");
      return res.json();
    },
    enabled: isCrmConnected && !!crmModule,
    staleTime: 5 * 60_000,
  });

  const variables: PromptVariable[] = useMemo(() => {
    const fields = fieldsData?.fields;
    if (!fields || fields.length === 0) return [];

    return fields
      .filter((f) => !EXCLUDED_FIELDS.has(f.api_name))
      .filter((f) => !f.api_name.startsWith("$"))
      .filter((f) => USEFUL_DATA_TYPES.has(f.data_type) || !f.read_only)
      .map((f) => ({
        name: f.api_name,
        description: `${f.display_label} (${crmModule} · ${f.data_type})`,
        defaultValue: "",
        category: "crm" as const,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [fieldsData, crmModule]);

  return {
    variables,
    isLoading: checkingCrm || loadingFields,
    isCrmConnected,
  };
}
