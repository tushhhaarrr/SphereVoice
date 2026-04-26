"use client";

/**
 * Agent CRM Tab — Dedicated tab for CRM read/write field configuration.
 *
 * Two clear sections:
 * 1. **Read Fields** — Map CRM record fields → agent prompt {{variables}}
 *    (e.g., CRM "Company" → agent variable {{lead_company}})
 * 2. **Write Fields** — Map post-call extracted data → CRM fields
 *    (e.g., extracted "call_summary" → CRM "Description")
 */

import { useCallback, useMemo, useState } from "react";
import {
    ArrowDown,
    ArrowRight,
    ArrowUp,
    Check,
    Database,
    Download,
    Loader2,
    Plus,
    Sparkles,
    Trash2,
    Upload,
    X,
    Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    useAgentPromptVariables,
    useAiCrmMapping,
    useCrmModuleFields,
} from "@/modules/campaigns/hooks/use-campaigns";
import { useCrmIntegrations } from "@/modules/integrations";
import type { PromptVariable } from "./prompt-editor";
import type { CrmWritebackSettings, ExtractionField, PostCallExtractionSettings } from "./agent-settings";

// ── Types ───────────────────────────────────────────────────

/**
 * Maps Post-Call Extraction default toggle keys → field names that the backend
 * extracts for each group. Mirrors backend/app/modules/pipeline/extraction_templates.py
 */
const DEFAULT_GROUP_FIELDS: Record<string, string[]> = {
    callSummary: ["call_summary", "key_topics", "caller_intent", "call_outcome"],
    successEvaluation: ["call_successful", "success_score", "success_description"],
    customerSentiment: ["customer_sentiment"],
    customerFrustrated: ["customer_frustrated"],
    agentPerformance: ["script_followed", "agent_tone", "agent_errors"],
    actionItems: ["action_items", "follow_up_needed"],
    callerInfo: ["caller_name", "caller_email", "caller_phone"],
};

/** Derive all active extraction field names from the Post-Call Extraction settings */
function getActiveExtractionFieldNames(pce?: PostCallExtractionSettings): string[] {
    if (!pce?.enabled) return [];
    const names: string[] = [];
    // Default fields — enabled by toggle
    for (const [group, fields] of Object.entries(DEFAULT_GROUP_FIELDS)) {
        if (pce.defaults[group]) {
            names.push(...fields);
        }
    }
    // Custom fields
    for (const f of pce.customFields ?? []) {
        if (f.name) names.push(f.name);
    }
    return names;
}

export interface CrmReadMapping {
    /** CRM module to read from (Leads, Contacts, Deals) */
    crmModule: string;
    /** Map: agent variable name → CRM field api_name */
    mapping: Record<string, string>;
}

const CRM_MODULES = [
    { value: "Leads", label: "Leads" },
    { value: "Contacts", label: "Contacts" },
    { value: "Deals", label: "Deals" },
];

// ── Main Component ──────────────────────────────────────────

interface AgentCrmTabProps {
    agentId: string;
    tenantId?: string;
    /** Prompt variables defined on the agent */
    variables: PromptVariable[];
    /** CRM read mapping config */
    readMapping: CrmReadMapping;
    onReadMappingChange: (mapping: CrmReadMapping) => void;
    /** CRM writeback config (from agent settings) */
    writebackSettings: CrmWritebackSettings;
    onWritebackChange: (patch: Partial<CrmWritebackSettings>) => void;
    /** Post-Call Extraction settings (to derive active fields including defaults) */
    postCallExtraction?: PostCallExtractionSettings;
    /** Navigate to Behavior tab to configure extraction fields */
    onNavigateToExtraction?: () => void;
    /** Callback to add custom extraction fields (creates them in Behavior settings) */
    onAddExtractionFields?: (fields: ExtractionField[]) => void;
    readOnly?: boolean;
}

export function AgentCrmTab({
    agentId,
    tenantId,
    variables,
    readMapping,
    onReadMappingChange,
    writebackSettings,
    onWritebackChange,
    postCallExtraction,
    onNavigateToExtraction,
    onAddExtractionFields,
    readOnly = false,
}: AgentCrmTabProps) {
    // Check CRM connection status
    const { data: crmIntegrations } = useCrmIntegrations(tenantId);
    const isCrmConnected = crmIntegrations?.integrations?.some(
        (i) => i.status === "connected",
    ) ?? false;

    if (!isCrmConnected) {
        return (
            <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
                    <Database className="h-6 w-6 text-muted-foreground" />
                </div>
                <h3 className="text-sm font-medium mb-1">No CRM Connected</h3>
                <p className="text-xs text-muted-foreground max-w-sm">
                    Connect a CRM (Zoho, HubSpot, or Salesforce) in Settings → Integrations
                    to configure read and write field mappings.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Section 1: Read Fields */}
            <ReadFieldsSection
                agentId={agentId}
                tenantId={tenantId}
                variables={variables}
                readMapping={readMapping}
                onChange={onReadMappingChange}
                readOnly={readOnly}
            />

            <Separator />

            {/* Section 2: Write Fields */}
            <WriteFieldsSection
                agentId={agentId}
                tenantId={tenantId}
                settings={writebackSettings}
                onChange={onWritebackChange}
                postCallExtraction={postCallExtraction}
                onNavigateToExtraction={onNavigateToExtraction}
                onAddExtractionFields={onAddExtractionFields}
                readMapping={readMapping}
                readOnly={readOnly}
            />
        </div>
    );
}

// ── Read Fields Section ─────────────────────────────────────

function ReadFieldsSection({
    agentId,
    tenantId,
    variables,
    readMapping,
    onChange,
    readOnly,
}: {
    agentId: string;
    tenantId?: string;
    variables: PromptVariable[];
    readMapping: CrmReadMapping;
    onChange: (mapping: CrmReadMapping) => void;
    readOnly: boolean;
}) {
    const [newVariable, setNewVariable] = useState("");
    const [newCrmField, setNewCrmField] = useState("");
    const aiMapping = useAiCrmMapping();

    const { data: fieldsData, isLoading: fieldsLoading } = useCrmModuleFields(
        readMapping.crmModule || "Leads",
        tenantId,
    );

    const crmFields = fieldsData?.fields ?? [];
    const entries = Object.entries(readMapping.mapping);
    const mappedVars = new Set(entries.map(([k]) => k));

    // Variables that are user-defined (not system auto-filled) and unmapped
    const unmappedVars = variables
        .filter((v) => !v.name.startsWith("current_") && v.name !== "agent_name" && v.name !== "company_name" && v.name !== "caller_number")
        .filter((v) => !mappedVars.has(v.name));

    function addMapping() {
        if (!newVariable || !newCrmField) return;
        onChange({
            ...readMapping,
            mapping: { ...readMapping.mapping, [newVariable]: newCrmField },
        });
        setNewVariable("");
        setNewCrmField("");
    }

    function removeMapping(key: string) {
        const updated = { ...readMapping.mapping };
        delete updated[key];
        onChange({ ...readMapping, mapping: updated });
    }

    function autoMap() {
        const newMappings: Record<string, string> = { ...readMapping.mapping };
        for (const v of variables) {
            if (newMappings[v.name]) continue;
            // Try to match variable name to CRM field by exact name or label
            const match = crmFields.find(
                (f) =>
                    f.api_name.toLowerCase() === v.name.toLowerCase() ||
                    f.display_label.toLowerCase().replace(/\s+/g, "_") === v.name.toLowerCase() ||
                    // Common aliases
                    (v.name === "lead_email" && f.api_name === "Email") ||
                    (v.name === "lead_company" && (f.api_name === "Company" || f.api_name === "Account_Name")) ||
                    (v.name === "lead_name" && f.api_name === "Full_Name") ||
                    (v.name === "lead_phone" && (f.api_name === "Phone" || f.api_name === "Mobile")) ||
                    (v.name === "caller_name" && f.api_name === "Full_Name") ||
                    (v.name === "deal_stage" && (f.api_name === "Stage" || f.api_name === "Lead_Status")) ||
                    (v.name === "product_interest" && f.api_name === "Lead_Source") ||
                    (v.name === "last_interaction" && f.api_name === "Description"),
            );
            if (match) {
                newMappings[v.name] = match.api_name;
            }
        }
        onChange({ ...readMapping, mapping: newMappings });
    }

    function aiMap() {
        const sourceFields = unmappedVars.map((v) => ({
            name: v.name,
            description: v.description ?? "",
        }));
        const targetFields = crmFields.map((f) => ({
            api_name: f.api_name,
            display_label: f.display_label,
            data_type: f.data_type,
        }));
        aiMapping.mutate(
            { source_fields: sourceFields, crm_fields: targetFields, direction: "read" },
            {
                onSuccess: (data) => {
                    const merged = { ...readMapping.mapping, ...data.mappings };
                    onChange({ ...readMapping, mapping: merged });
                },
            },
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
                    <Download className="h-3.5 w-3.5 text-foreground" />
                </div>
                <div>
                    <h3 className="text-sm font-medium">Read Fields</h3>
                    <p className="text-[11px] text-muted-foreground">
                        Pull CRM data into agent variables before each call
                    </p>
                </div>
            </div>

            {/* CRM Module selector */}
            <div className="space-y-1.5">
                <Label className="text-xs">Source CRM Module</Label>
                <Select
                    value={readMapping.crmModule || "Leads"}
                    onValueChange={(v) => onChange({ ...readMapping, crmModule: v })}
                    disabled={readOnly}
                >
                    <SelectTrigger className="w-40">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {CRM_MODULES.map((m) => (
                            <SelectItem key={m.value} value={m.value}>
                                {m.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {fieldsLoading && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Loading CRM fields…
                </div>
            )}

            {/* Unmapped variables hint */}
            {unmappedVars.length > 0 && !fieldsLoading && (
                <div className="rounded-lg border bg-muted/50 p-3 space-y-2">
                    <p className="text-xs font-medium text-foreground">
                        {unmappedVars.length} prompt variable{unmappedVars.length > 1 ? "s" : ""} not mapped to CRM:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        {unmappedVars.map((v) => (
                            <Badge
                                key={v.name}
                                variant="outline"
                                className="text-xs font-mono"
                            >
                                {`{{${v.name}}}`}
                            </Badge>
                        ))}
                    </div>
                    {crmFields.length > 0 && (
                        <div className="flex gap-2 mt-1">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={autoMap}
                                disabled={readOnly}
                                className="gap-1.5"
                            >
                                <Zap className="h-3 w-3" />
                                Auto-Map
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={aiMap}
                                disabled={readOnly || aiMapping.isPending}
                                className="gap-1.5"
                            >
                                {aiMapping.isPending ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                    <Sparkles className="h-3 w-3" />
                                )}
                                AI Map
                            </Button>
                        </div>
                    )}
                </div>
            )}

            {/* Existing read mappings */}
            {entries.length > 0 && (
                <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Current Mappings</Label>
                    {entries.map(([varName, crmField]) => (
                        <div
                            key={varName}
                            className="flex items-center gap-2 rounded-md border px-3 py-2"
                        >
                            <Badge variant="secondary" className="text-[11px] font-mono shrink-0">
                                CRM: {crmField}
                            </Badge>
                            <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                            <Badge variant="outline" className="text-[11px] font-mono shrink-0">
                                {`{{${varName}}}`}
                            </Badge>
                            <div className="flex-1" />
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => removeMapping(varName)}
                                disabled={readOnly}
                                className="h-6 w-6 text-destructive"
                            >
                                <Trash2 className="h-3 w-3" />
                            </Button>
                        </div>
                    ))}
                </div>
            )}

            {/* Add new read mapping */}
            {!fieldsLoading && crmFields.length > 0 && variables.length > 0 && (
                <div className="rounded-lg border p-3 space-y-3">
                    <p className="text-xs font-medium text-muted-foreground">Add Mapping</p>
                    <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
                        <div className="space-y-1">
                            <Label className="text-[10px]">CRM Field</Label>
                            <Select value={newCrmField} onValueChange={setNewCrmField} disabled={readOnly}>
                                <SelectTrigger className="h-8 text-xs">
                                    <SelectValue placeholder="Select CRM field" />
                                </SelectTrigger>
                                <SelectContent>
                                    {crmFields.map((f) => (
                                        <SelectItem key={f.api_name} value={f.api_name}>
                                            {f.display_label} ({f.api_name})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground mb-2" />
                        <div className="space-y-1">
                            <Label className="text-[10px]">Agent Variable</Label>
                            <Select value={newVariable} onValueChange={setNewVariable} disabled={readOnly}>
                                <SelectTrigger className="h-8 text-xs">
                                    <SelectValue placeholder="Select variable" />
                                </SelectTrigger>
                                <SelectContent>
                                    {variables
                                        .filter((v) => !mappedVars.has(v.name))
                                        .map((v) => (
                                            <SelectItem key={v.name} value={v.name}>
                                                {`{{${v.name}}}`}
                                            </SelectItem>
                                        ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={addMapping}
                        disabled={readOnly || !newVariable || !newCrmField}
                        className="gap-1.5"
                    >
                        <Plus className="h-3 w-3" />
                        Add
                    </Button>
                </div>
            )}

            {variables.length === 0 && !fieldsLoading && (
                <p className="text-xs text-muted-foreground py-2">
                    No variables defined in the agent prompt. Add {`{{variables}}`} to your prompt first.
                </p>
            )}
        </div>
    );
}

// ── Write Fields Section ────────────────────────────────────

/** Convert CRM api_name (PascalCase/Snake) to a snake_case extraction field name */
function crmFieldToExtractionName(apiName: string): string {
    return apiName
        .replace(/__\w$/, "") // strip Zoho custom suffixes like __s
        .replace(/([a-z])([A-Z])/g, "$1_$2") // camelCase → snake
        .replace(/[\s-]+/g, "_")
        .toLowerCase();
}

/**
 * CRM fields that cannot be meaningfully extracted from a voice conversation.
 * These are system, structural, or identity fields that exist on the CRM record
 * but would never appear in call dialogue.
 */
const NON_EXTRACTABLE_CRM_PATTERNS: RegExp[] = [
    // Geo/address fields — not spoken in calls
    /latitude/i, /longitude/i, /^street$/i, /^city$/i, /^state$/i,
    /^country$/i, /^zip$/i, /^zip_code$/i, /postal/i,
    /^mailing_/i, /^other_city$/i, /^other_state$/i, /^other_country$/i, /^other_zip$/i,
    /address/i,  // catches all address sub-fields (Flat, House No, Street, etc.)
    // System/ownership fields
    /^owner$/i, /^lead_owner$/i, /^contact_owner$/i, /^created_by$/i,
    /^modified_by$/i, /^created_time$/i, /^modified_time$/i,
    /^record_image$/i, /^layout$/i, /^id$/i, /^approved$/i,
    // System activity / timestamp tracking fields
    /activity_time$/i, /^last_activity/i, /^last_enriched/i,
    /conversion_time$/i, /^lead_conversion/i, /^converted_date/i,
    /^call_duration$/i, /^average_time/i,
    /^change_log_time/i, /^locked__s$/i, /^tag$/i,
    // Identity sub-fields already covered by caller_name / caller_email / caller_phone
    /^first_name$/i, /^last_name$/i, /^full_name$/i,
    /^email$/i, /^secondary_email$/i,
    /^phone$/i, /^mobile$/i, /^other_phone$/i, /^home_phone$/i, /^asst_phone$/i,
    // Merge/conversion internal fields
    /^converted$/i, /^converted_detail$/i, /^converted_account$/i,
    /^converted_contact$/i, /^converted_deal$/i,
    // Tracking/social fields unlikely to come from a call
    /^fax$/i, /^skype_id$/i, /^twitter$/i, /^website$/i,
    /^unsubscribed_mode$/i, /^unsubscribed_time$/i,
    /^email_opt_out$/i, /^visitor_score$/i,
    /^days_visited$/i, /^first_visited/i, /^last_visited/i,
    /^referrer$/i, /^first_page_visited$/i,
    // Corporate data you can't learn from a voice call
    /^no_of_employees$/i, /^annual_revenue$/i, /^secondary_email$/i,
    // Structural fields
    /^salutation$/i, /^exchange_rate$/i, /^currency$/i,
    /^scoring_rule/i, /^territory/i,
];

/** Data types that are never extractable from voice (file uploads, images, etc.) */
const NON_EXTRACTABLE_DATA_TYPES = new Set([
    "fileupload", "imageupload", "profileimage", "lookup", "ownerlookup",
    "autonumber", "formula", "rollup_summary",
]);

/**
 * Returns true if a CRM field could plausibly be extracted from a voice call.
 * Filters out system fields, coordinates, owner/tracking fields, and
 * non-extractable data types like lookups and formulas.
 */
function isCrmFieldExtractable(apiName: string, dataType: string): boolean {
    if (NON_EXTRACTABLE_DATA_TYPES.has(dataType)) return false;
    return !NON_EXTRACTABLE_CRM_PATTERNS.some((re) => re.test(apiName));
}

/** Map CRM data_type to extraction field type */
function crmDataTypeToExtractionType(dataType: string): ExtractionField["type"] {
    switch (dataType) {
        case "boolean":
            return "boolean";
        case "integer":
        case "bigint":
        case "number":
        case "double":
        case "currency":
            return "number";
        default:
            return "string";
    }
}

/** Build a specific, LLM-friendly extraction description from CRM field metadata */
function buildExtractionDescription(crmField: {
    api_name: string;
    display_label: string;
    data_type: string;
}): string {
    const label = crmField.display_label;
    const dt = crmField.data_type;

    // Data-type-specific guidance so the LLM returns the right format
    if (dt === "boolean") {
        return `Whether the "${label}" applies based on the conversation. Return true or false`;
    }
    if (dt === "integer" || dt === "bigint" || dt === "number" || dt === "double") {
        return `The numeric value for "${label}" discussed or inferred from the call. Return a number, or null if not mentioned`;
    }
    if (dt === "currency") {
        return `The monetary amount for "${label}" mentioned during the call. Return the numeric value without currency symbol, or null if not discussed`;
    }
    if (dt === "date" || dt === "datetime") {
        return `The date/time for "${label}" mentioned during the call. Return in ISO 8601 format (YYYY-MM-DD), or null if not mentioned`;
    }
    if (dt === "email") {
        return `The email address for "${label}" provided during the conversation. Null if not mentioned`;
    }
    if (dt === "phone") {
        return `The phone number for "${label}" provided during the conversation. Null if not mentioned`;
    }
    if (dt === "picklist" || dt === "multiselectpicklist" || dt === "enum") {
        return `The value for "${label}" based on the conversation. Pick the most appropriate option. Null if not determinable`;
    }
    if (dt === "textarea" || dt === "text") {
        return `The "${label}" information extracted from the conversation. Provide a concise, factual summary. Null if not discussed`;
    }
    // Fallback for unknown types
    return `The "${label}" as discussed or inferred from the call conversation. Null if not mentioned or not applicable`;
}

function WriteFieldsSection({
    agentId,
    tenantId,
    settings,
    onChange,
    postCallExtraction,
    onNavigateToExtraction,
    onAddExtractionFields,
    readMapping,
    readOnly,
}: {
    agentId: string;
    tenantId?: string;
    settings: CrmWritebackSettings;
    onChange: (patch: Partial<CrmWritebackSettings>) => void;
    postCallExtraction?: PostCallExtractionSettings;
    onNavigateToExtraction?: () => void;
    onAddExtractionFields?: (fields: ExtractionField[]) => void;
    readMapping?: CrmReadMapping;
    readOnly: boolean;
}) {
    const [newExtracted, setNewExtracted] = useState("");
    const [newCrmField, setNewCrmField] = useState("");
    const aiMapping = useAiCrmMapping();

    // Confirmation state for "Create Extraction Fields & Map"
    const [pendingCrmFieldNames, setPendingCrmFieldNames] = useState<Set<string> | null>(null);

    const { data: promptData, isLoading: varsLoading } = useAgentPromptVariables(
        agentId,
    );
    const { data: fieldsData, isLoading: fieldsLoading } = useCrmModuleFields(
        settings.crmModule || "Leads",
        tenantId,
    );

    // Merge: local active fields (defaults + custom) + API extraction_fields (saved)
    const localFields = getActiveExtractionFieldNames(postCallExtraction);
    const apiFields = (promptData?.extraction_fields ?? [])
        .map((f) => (f as { name?: string; description?: string }).name || "")
        .filter(Boolean);
    const extractionFields = [...new Set([...localFields, ...apiFields])];
    const readMappedCrmFields = new Set(
        Object.values(readMapping?.mapping ?? {}),
    );
    const writableCrmFields = (fieldsData?.fields ?? []).filter(
        (f) => !f.read_only,
    );
    // CRM fields available for writing — excludes any field already used as a read source
    const availableWriteCrmFields = writableCrmFields.filter(
        (f) => !readMappedCrmFields.has(f.api_name),
    );
    const entries = Object.entries(settings.mapping);
    const mappedExtractions = new Set(entries.map(([k]) => k));
    const mappedCrmTargets = new Set(entries.map(([, v]) => v));
    const unmappedExtractions = extractionFields.filter(
        (f) => !mappedExtractions.has(f),
    );
    // CRM fields not yet mapped — filtered to only those plausibly extractable from a call
    // Also excludes fields whose snake_case name already matches an existing extraction field
    const extractionFieldSet = new Set(extractionFields);
    const unmappedCrmFields = availableWriteCrmFields.filter(
        (f) =>
            !mappedCrmTargets.has(f.api_name) &&
            isCrmFieldExtractable(f.api_name, f.data_type) &&
            !extractionFieldSet.has(crmFieldToExtractionName(f.api_name)),
    );

    function addMapping() {
        if (!newExtracted || !newCrmField) return;
        onChange({
            mapping: { ...settings.mapping, [newExtracted]: newCrmField },
        });
        setNewExtracted("");
        setNewCrmField("");
    }

    function removeMapping(key: string) {
        const updated = { ...settings.mapping };
        delete updated[key];
        onChange({ mapping: updated });
    }

    function autoMap() {
        const newMappings: Record<string, string> = { ...settings.mapping };
        // Smart aliases: extraction field → likely CRM field api_names
        const WRITE_ALIASES: Record<string, string[]> = {
            call_summary: ["Call_Summary", "Description", "Notes"],
            call_outcome: ["Call_Result", "Call_Outcome", "Result", "Outcome"],
            caller_intent: ["Lead_Source", "Intent", "Caller_Intent"],
            caller_name: ["Full_Name", "Last_Name", "First_Name"],
            caller_email: ["Email", "Secondary_Email"],
            caller_phone: ["Phone", "Mobile", "Other_Phone"],
            customer_sentiment: ["Sentiment", "Customer_Sentiment", "Rating"],
            customer_frustrated: ["Frustrated", "Customer_Frustrated"],
            action_items: ["Action_Items", "Next_Steps", "Follow_Up"],
            follow_up_needed: ["Follow_Up_Needed", "Requires_Follow_Up"],
            call_successful: ["Call_Successful", "Converted"],
            success_score: ["Success_Score", "Score", "Rating"],
            key_topics: ["Key_Topics", "Topics"],
        };
        for (const fieldName of extractionFields) {
            if (newMappings[fieldName]) continue;
            // 1. Exact name match (skip fields already used as read sources)
            const exactMatch = availableWriteCrmFields.find(
                (f) =>
                    f.api_name.toLowerCase() === fieldName.toLowerCase() ||
                    f.display_label.toLowerCase().replace(/\s+/g, "_") === fieldName.toLowerCase(),
            );
            if (exactMatch) {
                newMappings[fieldName] = exactMatch.api_name;
                continue;
            }
            // 2. Alias match (skip fields already used as read sources)
            const aliases = WRITE_ALIASES[fieldName];
            if (aliases) {
                const aliasMatch = availableWriteCrmFields.find((f) =>
                    aliases.some((a) => f.api_name.toLowerCase() === a.toLowerCase()),
                );
                if (aliasMatch) {
                    newMappings[fieldName] = aliasMatch.api_name;
                }
            }
        }
        onChange({ mapping: newMappings });
    }

    /** Step 1: Compute candidates and open confirmation picker */
    function startCreateFieldsFlow() {
        const candidates = unmappedCrmFields.filter((crmF) => {
            const candidateName = crmFieldToExtractionName(crmF.api_name);
            return !extractionFields.includes(candidateName) && !mappedExtractions.has(candidateName);
        });
        if (candidates.length === 0) return;
        setPendingCrmFieldNames(new Set(candidates.map((f) => f.api_name)));
    }

    /** Step 2: Create only the confirmed fields */
    function confirmCreateFields() {
        if (!onAddExtractionFields || !pendingCrmFieldNames) return;
        const toCreate = unmappedCrmFields.filter((f) => pendingCrmFieldNames.has(f.api_name));
        if (toCreate.length === 0) {
            setPendingCrmFieldNames(null);
            return;
        }

        const newFields: ExtractionField[] = toCreate.map((crmF) => ({
            name: crmFieldToExtractionName(crmF.api_name),
            type: crmDataTypeToExtractionType(crmF.data_type),
            description: buildExtractionDescription(crmF),
        }));

        // 1. Add custom extraction fields
        onAddExtractionFields(newFields);

        // 2. Auto-map them to the corresponding CRM fields
        const newMappings: Record<string, string> = { ...settings.mapping };
        for (let i = 0; i < toCreate.length; i++) {
            newMappings[newFields[i].name] = toCreate[i].api_name;
        }
        onChange({ mapping: newMappings });
        setPendingCrmFieldNames(null);
    }

    function aiMap() {
        const sourceFields = unmappedExtractions.map((name) => ({
            name,
            description: "",
        }));
        const targetFields = availableWriteCrmFields.map((f) => ({
            api_name: f.api_name,
            display_label: f.display_label,
            data_type: f.data_type,
        }));
        aiMapping.mutate(
            { source_fields: sourceFields, crm_fields: targetFields, direction: "write" },
            {
                onSuccess: (data) => {
                    onChange({ mapping: { ...settings.mapping, ...data.mappings } });
                },
            },
        );
    }

    const isLoading = varsLoading || fieldsLoading;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
                        <Upload className="h-3.5 w-3.5 text-foreground" />
                    </div>
                    <div>
                        <h3 className="text-sm font-medium">Write Fields</h3>
                        <p className="text-[11px] text-muted-foreground">
                            Push extracted call data back to CRM after each call
                        </p>
                    </div>
                </div>
                <Switch
                    checked={settings.enabled}
                    onCheckedChange={(v) => onChange({ enabled: v })}
                    disabled={readOnly}
                />
            </div>

            {settings.enabled && (
                <>
                    {/* Target Module */}
                    <div className="space-y-1.5">
                        <Label className="text-xs">Target CRM Module</Label>
                        <Select
                            value={settings.crmModule || "Leads"}
                            onValueChange={(v) => onChange({ crmModule: v })}
                            disabled={readOnly}
                        >
                            <SelectTrigger className="w-40">
                                <SelectValue placeholder="Select module" />
                            </SelectTrigger>
                            <SelectContent>
                                {CRM_MODULES.map((m) => (
                                    <SelectItem key={m.value} value={m.value}>
                                        {m.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {isLoading && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Loading fields…
                        </div>
                    )}

                    {/* Unmapped extraction fields */}
                    {unmappedExtractions.length > 0 && !isLoading && (
                        <div className="rounded-lg border bg-muted/50 p-3 space-y-2">
                            <p className="text-xs font-medium text-foreground">
                                {unmappedExtractions.length} extracted field{unmappedExtractions.length > 1 ? "s" : ""} not mapped:
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                                {unmappedExtractions.map((f) => (
                                    <Badge
                                        key={f}
                                        variant="outline"
                                        className="text-xs font-mono"
                                    >
                                        {f}
                                    </Badge>
                                ))}
                            </div>
                            {writableCrmFields.length > 0 && (
                                <div className="flex gap-2 mt-1">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={autoMap}
                                        disabled={readOnly}
                                        className="gap-1.5"
                                    >
                                        <Zap className="h-3 w-3" />
                                        Auto-Map
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={aiMap}
                                        disabled={readOnly || aiMapping.isPending}
                                        className="gap-1.5"
                                    >
                                        {aiMapping.isPending ? (
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                        ) : (
                                            <Sparkles className="h-3 w-3" />
                                        )}
                                        AI Map
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* CRM fields with no extraction field to feed them */}
                    {onAddExtractionFields && unmappedCrmFields.length > 0 && !isLoading && (
                        <div className="rounded-lg border border-dashed bg-muted/30 p-3 space-y-2">
                            {pendingCrmFieldNames === null ? (
                                <>
                                    <p className="text-xs font-medium text-foreground">
                                        {unmappedCrmFields.length} CRM field{unmappedCrmFields.length > 1 ? "s" : ""} have no
                                        extraction field to write to them:
                                    </p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {unmappedCrmFields.slice(0, 12).map((f) => (
                                            <Badge
                                                key={f.api_name}
                                                variant="outline"
                                                className="text-xs font-mono"
                                            >
                                                {f.display_label}
                                            </Badge>
                                        ))}
                                        {unmappedCrmFields.length > 12 && (
                                            <span className="text-[11px] text-muted-foreground">
                                                +{unmappedCrmFields.length - 12} more
                                            </span>
                                        )}
                                    </div>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={startCreateFieldsFlow}
                                        disabled={readOnly}
                                        className="gap-1.5"
                                    >
                                        <Plus className="h-3 w-3" />
                                        Create Extraction Fields &amp; Map…
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <p className="text-xs font-medium text-foreground">
                                        Select which CRM fields to create extraction fields for:
                                    </p>
                                    <p className="text-[10px] text-muted-foreground">
                                        The AI will extract these from each call and write them back to CRM. Remove any you don&apos;t need.
                                    </p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {unmappedCrmFields
                                            .filter((f) => pendingCrmFieldNames.has(f.api_name))
                                            .map((f) => (
                                                <Badge
                                                    key={f.api_name}
                                                    variant="secondary"
                                                    className="text-xs font-mono gap-1 pr-1 cursor-pointer hover:bg-destructive/10"
                                                    onClick={() => {
                                                        const next = new Set(pendingCrmFieldNames);
                                                        next.delete(f.api_name);
                                                        setPendingCrmFieldNames(next);
                                                    }}
                                                >
                                                    {f.display_label}
                                                    <X className="h-3 w-3 text-muted-foreground" />
                                                </Badge>
                                            ))}
                                        {/* Show removed fields as add-back buttons */}
                                        {unmappedCrmFields
                                            .filter((f) => !pendingCrmFieldNames.has(f.api_name))
                                            .map((f) => (
                                                <Badge
                                                    key={f.api_name}
                                                    variant="outline"
                                                    className="text-xs font-mono gap-1 pr-1 cursor-pointer opacity-40 hover:opacity-100"
                                                    onClick={() => {
                                                        const next = new Set(pendingCrmFieldNames);
                                                        next.add(f.api_name);
                                                        setPendingCrmFieldNames(next);
                                                    }}
                                                >
                                                    {f.display_label}
                                                    <Plus className="h-3 w-3 text-muted-foreground" />
                                                </Badge>
                                            ))}
                                    </div>
                                    <div className="flex gap-2 mt-1">
                                        <Button
                                            variant="default"
                                            size="sm"
                                            onClick={confirmCreateFields}
                                            disabled={readOnly || pendingCrmFieldNames.size === 0}
                                            className="gap-1.5"
                                        >
                                            <Check className="h-3 w-3" />
                                            Create {pendingCrmFieldNames.size} Field{pendingCrmFieldNames.size !== 1 ? "s" : ""} &amp; Map
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setPendingCrmFieldNames(null)}
                                        >
                                            Cancel
                                        </Button>
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {/* Existing write mappings */}
                    {entries.length > 0 && (
                        <div className="space-y-1.5">
                            <Label className="text-xs text-muted-foreground">Current Mappings</Label>
                            {entries.map(([extracted, crmField]) => (
                                <div
                                    key={extracted}
                                    className="flex items-center gap-2 rounded-md border px-3 py-2"
                                >
                                    <Badge variant="secondary" className="text-[11px] font-mono shrink-0">
                                        {extracted}
                                    </Badge>
                                    <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                                    <span className="text-xs flex-1">{crmField}</span>
                                    {readMappedCrmFields.has(crmField) && (
                                        <span className="text-[10px] text-destructive font-medium shrink-0">
                                            ⚠ also a read field
                                        </span>
                                    )}
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => removeMapping(extracted)}
                                        disabled={readOnly}
                                        className="h-6 w-6 text-destructive"
                                    >
                                        <Trash2 className="h-3 w-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Add new write mapping */}
                    {!isLoading && extractionFields.length > 0 && settings.crmModule && (
                        <div className="rounded-lg border p-3 space-y-3">
                            <p className="text-xs font-medium text-muted-foreground">Add Mapping</p>
                            <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
                                <div className="space-y-1">
                                    <Label className="text-[10px]">Extracted Field</Label>
                                    <Select value={newExtracted} onValueChange={setNewExtracted} disabled={readOnly}>
                                        <SelectTrigger className="h-8 text-xs">
                                            <SelectValue placeholder="Select field" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {extractionFields.map((f) => (
                                                <SelectItem key={f} value={f} disabled={mappedExtractions.has(f)}>
                                                    {f}{mappedExtractions.has(f) ? " (mapped)" : ""}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground mb-2" />
                                <div className="space-y-1">
                                    <Label className="text-[10px]">CRM Field</Label>
                                    <Select value={newCrmField} onValueChange={setNewCrmField} disabled={readOnly}>
                                        <SelectTrigger className="h-8 text-xs">
                                            <SelectValue placeholder="Select CRM field" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {availableWriteCrmFields.map((f) => (
                                                <SelectItem key={f.api_name} value={f.api_name}>
                                                    {f.display_label} ({f.api_name})
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={addMapping}
                                disabled={readOnly || !newExtracted || !newCrmField}
                                className="gap-1.5"
                            >
                                <Plus className="h-3 w-3" />
                                Add
                            </Button>
                        </div>
                    )}

                    {!isLoading && extractionFields.length === 0 && (
                        <div className="rounded-lg border border-dashed p-4 text-center space-y-3">
                            <p className="text-xs text-muted-foreground">
                                No extraction fields defined yet. Configure what data to extract
                                from calls first.
                            </p>
                            {onNavigateToExtraction && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={onNavigateToExtraction}
                                    className="gap-1.5"
                                >
                                    <ArrowRight className="h-3 w-3" />
                                    Go to Behavior → Post-Call Extraction
                                </Button>
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
