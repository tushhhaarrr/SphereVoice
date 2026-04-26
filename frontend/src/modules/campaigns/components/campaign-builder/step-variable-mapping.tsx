"use client";

import { useState } from "react";
import { ArrowRight, Plus, Trash2, Loader2, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useAgentPromptVariables, useCrmModuleFields } from "../../hooks/use-campaigns";
import type { CampaignWizardData } from "../../types";

const SOURCE_LABELS: Record<string, string> = {
    system_prompt: "System Prompt",
    global_prompt: "Global Prompt",
    welcome_message: "Welcome Message",
    defined: "Agent Variables",
};

function getSourceLabel(source: string): string {
    if (source.startsWith("node:")) return `Flow Node: ${source.slice(5)}`;
    return SOURCE_LABELS[source] || source;
}

export interface StepVariableMappingProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
    tenantId: string;
}

export function StepVariableMapping({
    data,
    onUpdate,
    tenantId,
}: StepVariableMappingProps) {
    const [newVarName, setNewVarName] = useState("");
    const [newCrmField, setNewCrmField] = useState("");

    const { data: promptData, isLoading: varsLoading } = useAgentPromptVariables(
        data.agent_id
    );
    const crmModule = (data.source_config?.module as string) || "";
    const { data: fieldsData, isLoading: fieldsLoading } = useCrmModuleFields(
        crmModule,
        tenantId
    );

    const promptVariables = promptData?.prompt_variables ?? [];
    const varsBySource = promptData?.vars_by_source ?? {};
    const definedVars = promptData?.defined_variables ?? [];
    const crmFields = (fieldsData?.fields ?? []).filter((f) => !f.read_only);
    const entries = Object.entries(data.variable_mapping);
    const mappedVars = new Set(entries.map(([k]) => k));
    const unmappedVars = promptVariables.filter((v) => !mappedVars.has(v));

    // Build a reverse lookup: variable → sources it appears in
    const varSources: Record<string, string[]> = {};
    for (const [source, vars] of Object.entries(varsBySource)) {
        for (const v of vars) {
            varSources[v] = varSources[v] || [];
            varSources[v].push(source);
        }
    }

    // Find defined variables with default values
    const defaultsMap: Record<string, string> = {};
    for (const dv of definedVars) {
        if (dv.default_value) defaultsMap[dv.name] = dv.default_value;
    }

    function addMapping() {
        if (!newVarName || !newCrmField) return;
        onUpdate({
            variable_mapping: {
                ...data.variable_mapping,
                [newVarName]: newCrmField,
            },
        });
        setNewVarName("");
        setNewCrmField("");
    }

    function removeMapping(key: string) {
        const updated = { ...data.variable_mapping };
        delete updated[key];
        onUpdate({ variable_mapping: updated });
    }

    // Common aliases: prompt variable name → likely CRM field API names
    const VARIABLE_ALIASES: Record<string, string[]> = {
        caller_name: ["Full_Name", "Name", "Contact_Name", "firstname", "first_name"],
        lead_name: ["Full_Name", "Name", "Contact_Name", "Lead_Name"],
        company_name: ["Company", "Account_Name", "company"],
        lead_company: ["Company", "Account_Name", "company"],
        lead_email: ["Email", "email", "Work_Email"],
        lead_phone: ["Phone", "Mobile", "phone", "mobile"],
        product_interest: ["Product_Interest", "Interest", "Product", "product_interest"],
        deal_stage: ["Stage", "Lead_Status", "Deal_Stage", "Pipeline_Stage"],
        appointment_date: ["Appointment_Date", "Meeting_Date", "appointment_date"],
        last_interaction: ["Last_Activity_Time", "Last_Interaction", "Description"],
    };

    function autoMap() {
        const newMappings: Record<string, string> = { ...data.variable_mapping };
        for (const varName of promptVariables) {
            if (newMappings[varName]) continue;
            // 1. Exact match on api_name or display_label
            const exactMatch = crmFields.find(
                (f) =>
                    f.api_name.toLowerCase() === varName.toLowerCase() ||
                    f.display_label.toLowerCase().replace(/\s+/g, "_") === varName.toLowerCase()
            );
            if (exactMatch) {
                newMappings[varName] = exactMatch.api_name;
                continue;
            }
            // 2. Alias match — check known mappings
            const aliases = VARIABLE_ALIASES[varName];
            if (aliases) {
                const aliasMatch = crmFields.find((f) =>
                    aliases.some((a) => a.toLowerCase() === f.api_name.toLowerCase())
                );
                if (aliasMatch) {
                    newMappings[varName] = aliasMatch.api_name;
                }
            }
        }
        onUpdate({ variable_mapping: newMappings });
    }

    const isLoading = varsLoading || fieldsLoading;

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">Variable Mapping</h2>
                <p className="text-sm text-muted-foreground">
                    Map CRM fields to the agent&apos;s template variables. Variables found
                    in the system prompt, welcome message, and flow nodes will all be
                    resolved with CRM data for each contact.
                </p>
            </div>

            {isLoading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading agent variables and CRM fields...
                </div>
            )}

            {/* Variable discovery — show all found variables and their sources */}
            {!isLoading && promptVariables.length > 0 && (
                <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                    <div className="flex items-center gap-2">
                        <Info className="h-4 w-4 text-muted-foreground" />
                        <p className="text-sm font-medium">
                            {promptVariables.length} variable{promptVariables.length !== 1 ? "s" : ""} found in this agent
                        </p>
                    </div>
                    <div className="space-y-1.5">
                        {promptVariables.map((v) => {
                            const sources = varSources[v] || [];
                            const hasDefault = v in defaultsMap;
                            const isMapped = mappedVars.has(v);
                            return (
                                <div key={v} className="flex items-center gap-2 text-sm">
                                    <Badge
                                        variant={isMapped ? "default" : "outline"}
                                        className={`text-xs font-mono shrink-0 ${!isMapped ? "border-amber-300 dark:border-amber-700" : ""
                                            }`}
                                    >
                                        {`{{${v}}}`}
                                    </Badge>
                                    <span className="text-xs text-muted-foreground">
                                        {sources.map(getSourceLabel).join(", ")}
                                    </span>
                                    {hasDefault && !isMapped && (
                                        <span className="text-xs text-muted-foreground italic">
                                            default: &quot;{defaultsMap[v]}&quot;
                                        </span>
                                    )}
                                    {isMapped && (
                                        <span className="text-xs text-green-600 dark:text-green-400">
                                            mapped
                                        </span>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Unmapped variables warning */}
            {unmappedVars.length > 0 && !isLoading && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 p-3 space-y-2">
                    <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
                        {unmappedVars.length} unmapped variable{unmappedVars.length > 1 ? "s" : ""}
                        {unmappedVars.every((v) => v in defaultsMap)
                            ? " (all have defaults — mapping is optional)"
                            : " — unmapped variables without defaults will not be resolved"}
                    </p>
                    {crmFields.length > 0 && (
                        <Button variant="outline" size="sm" onClick={autoMap} className="mt-1">
                            Auto-Map Matching Fields
                        </Button>
                    )}
                </div>
            )}

            {/* Existing mappings */}
            {entries.length > 0 && (
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Current Mappings</Label>
                    {entries.map(([varName, crmField]) => (
                        <div
                            key={varName}
                            className="flex items-center gap-2 rounded-md border px-3 py-2"
                        >
                            <Badge variant="secondary" className="text-xs font-mono shrink-0">
                                {`{{${varName}}}`}
                            </Badge>
                            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                            <span className="flex-1 text-sm">{crmField}</span>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => removeMapping(varName)}
                                className="h-7 w-7 text-destructive"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    ))}
                </div>
            )}

            {/* Add new mapping */}
            {!isLoading && promptVariables.length > 0 && (
                <div className="space-y-3 rounded-lg border p-4">
                    <p className="text-xs font-medium text-muted-foreground">Add Mapping</p>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                            <Label>Prompt Variable</Label>
                            <Select
                                value={newVarName}
                                onValueChange={setNewVarName}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select variable" />
                                </SelectTrigger>
                                <SelectContent>
                                    {promptVariables.map((v) => (
                                        <SelectItem
                                            key={v}
                                            value={v}
                                            disabled={mappedVars.has(v)}
                                        >
                                            {`{{${v}}}`}
                                            {mappedVars.has(v) ? " (mapped)" : ""}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1.5">
                            <Label>CRM Field</Label>
                            <Select
                                value={newCrmField}
                                onValueChange={setNewCrmField}
                            >
                                <SelectTrigger>
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
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={addMapping}
                        disabled={!newVarName || !newCrmField}
                    >
                        <Plus className="mr-1.5 h-3.5 w-3.5" />
                        Add Mapping
                    </Button>
                </div>
            )}

            {!isLoading && promptVariables.length === 0 && crmModule && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-4 space-y-2">
                    <p className="text-sm font-medium text-blue-800 dark:text-blue-300">
                        No template variables found in this agent
                    </p>
                    <p className="text-xs text-blue-700 dark:text-blue-400">
                        Add <code className="text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">
                            {`{{variable_name}}`}</code> placeholders to the agent&apos;s
                        <strong> system prompt</strong>, <strong>welcome message</strong>,
                        or <strong>flow node prompts</strong> to inject CRM data into each
                        call. For example:{" "}
                        <code className="text-xs bg-blue-100 dark:bg-blue-900 px-1 rounded">
                            {`Hi {{First_Name}}, I'm calling from {{Company}}...`}
                        </code>
                    </p>
                </div>
            )}

            {!crmModule && data.source_type === "zoho_crm" && (
                <p className="text-sm text-muted-foreground">
                    Select a CRM module in the previous step to see available fields.
                </p>
            )}
        </div>
    );
}
