"use client";

import { useState } from "react";
import { ArrowRight, Plus, Trash2, Loader2, Sparkles } from "lucide-react";
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
import { useAgentPromptVariables, useAiCrmMapping, useCrmModuleFields } from "../../hooks/use-campaigns";
import type { CampaignWizardData } from "../../types";

export interface StepWritebackMappingProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
    tenantId: string;
}

export function StepWritebackMapping({
    data,
    onUpdate,
    tenantId,
}: StepWritebackMappingProps) {
    const [newExtracted, setNewExtracted] = useState("");
    const [newCrmField, setNewCrmField] = useState("");
    const aiMapping = useAiCrmMapping();

    const { data: promptData, isLoading: varsLoading } = useAgentPromptVariables(
        data.agent_id
    );
    const crmModule = (data.source_config?.module as string) || "";
    const { data: fieldsData, isLoading: fieldsLoading } = useCrmModuleFields(
        crmModule,
        tenantId
    );

    const extractionFieldObjs = (promptData?.extraction_fields ?? []) as {
        name?: string;
        description?: string;
    }[];
    const extractionFields = extractionFieldObjs
        .map((f) => f.name || "")
        .filter(Boolean);
    const writableCrmFields = (fieldsData?.fields ?? []).filter(
        (f) => !f.read_only
    );
    const entries = Object.entries(data.writeback_mapping);
    const mappedExtractions = new Set(entries.map(([k]) => k));
    const unmappedExtractions = extractionFields.filter(
        (f) => !mappedExtractions.has(f)
    );

    function addMapping() {
        if (!newExtracted || !newCrmField) return;
        onUpdate({
            writeback_mapping: {
                ...data.writeback_mapping,
                [newExtracted]: newCrmField,
            },
        });
        setNewExtracted("");
        setNewCrmField("");
    }

    function removeMapping(key: string) {
        const updated = { ...data.writeback_mapping };
        delete updated[key];
        onUpdate({ writeback_mapping: updated });
    }

    function autoMap() {
        const newMappings: Record<string, string> = { ...data.writeback_mapping };
        for (const fieldName of extractionFields) {
            if (newMappings[fieldName]) continue;
            const match = writableCrmFields.find(
                (f) =>
                    f.api_name.toLowerCase() === fieldName.toLowerCase() ||
                    f.display_label.toLowerCase().replace(/\s+/g, "_") === fieldName.toLowerCase()
            );
            if (match) {
                newMappings[fieldName] = match.api_name;
            }
        }
        onUpdate({ writeback_mapping: newMappings });
    }

    function aiMap() {
        const sourceFields = unmappedExtractions.map((name) => {
            const obj = extractionFieldObjs.find((f) => f.name === name);
            return { name, description: obj?.description ?? "" };
        });
        const targetFields = writableCrmFields.map((f) => ({
            api_name: f.api_name,
            display_label: f.display_label,
            data_type: f.data_type,
        }));
        aiMapping.mutate(
            { source_fields: sourceFields, crm_fields: targetFields, direction: "write" },
            {
                onSuccess: (result) => {
                    onUpdate({
                        writeback_mapping: { ...data.writeback_mapping, ...result.mappings },
                    });
                },
            },
        );
    }

    const isLoading = varsLoading || fieldsLoading;

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">Write-Back Mapping</h2>
                <p className="text-sm text-muted-foreground">
                    Map the agent&apos;s extraction fields to CRM fields. After each
                    call, extracted data will be written back to the source CRM record.
                </p>
            </div>

            {isLoading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading extraction fields and CRM fields...
                </div>
            )}

            {/* Unmapped extraction fields info  */}
            {unmappedExtractions.length > 0 && !isLoading && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-3 space-y-2">
                    <p className="text-xs font-medium text-blue-800 dark:text-blue-300">
                        {unmappedExtractions.length} extraction field{unmappedExtractions.length > 1 ? "s" : ""} not
                        mapped to CRM:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        {unmappedExtractions.map((f) => (
                            <Badge key={f} variant="outline" className="text-xs font-mono border-blue-300 dark:border-blue-700">
                                {f}
                            </Badge>
                        ))}
                    </div>
                    {writableCrmFields.length > 0 && (
                        <div className="flex items-center gap-2 mt-1">
                            <Button variant="outline" size="sm" onClick={autoMap}>
                                Auto-Map Matching Fields
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={aiMap}
                                disabled={aiMapping.isPending}
                            >
                                {aiMapping.isPending ? (
                                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                ) : (
                                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                                )}
                                AI Map
                            </Button>
                        </div>
                    )}
                </div>
            )}

            {/* Existing mappings */}
            {entries.length > 0 && (
                <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Current Mappings</Label>
                    {entries.map(([extracted, crmField]) => (
                        <div
                            key={extracted}
                            className="flex items-center gap-2 rounded-md border px-3 py-2"
                        >
                            <Badge variant="secondary" className="text-xs font-mono shrink-0">
                                {extracted}
                            </Badge>
                            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                            <span className="flex-1 text-sm">{crmField}</span>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => removeMapping(extracted)}
                                className="h-7 w-7 text-destructive"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    ))}
                </div>
            )}

            {/* Add new mapping */}
            {!isLoading && extractionFields.length > 0 && (
                <div className="space-y-3 rounded-lg border p-4">
                    <p className="text-xs font-medium text-muted-foreground">Add Mapping</p>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                            <Label>Extracted Field</Label>
                            <Select
                                value={newExtracted}
                                onValueChange={setNewExtracted}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select extracted field" />
                                </SelectTrigger>
                                <SelectContent>
                                    {extractionFields.map((f) => (
                                        <SelectItem
                                            key={f}
                                            value={f}
                                            disabled={mappedExtractions.has(f)}
                                        >
                                            {f}
                                            {mappedExtractions.has(f) ? " (mapped)" : ""}
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
                                    {writableCrmFields.map((f) => (
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
                        disabled={!newExtracted || !newCrmField}
                    >
                        <Plus className="mr-1.5 h-3.5 w-3.5" />
                        Add Mapping
                    </Button>
                </div>
            )}

            {!isLoading && extractionFields.length === 0 && (
                <div className="rounded-lg border border-dashed p-4 text-center">
                    <p className="text-sm text-muted-foreground">
                        No extraction fields defined on the selected agent.
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                        Configure extraction fields in the agent&apos;s post-call settings
                        to enable CRM write-back.
                    </p>
                </div>
            )}

            {!crmModule && data.source_type === "zoho_crm" && !isLoading && (
                <p className="text-sm text-muted-foreground">
                    Select a CRM module in Step 2 to see available fields for write-back.
                </p>
            )}
        </div>
    );
}
