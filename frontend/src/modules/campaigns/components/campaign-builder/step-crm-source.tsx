"use client";

import { Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useCrmIntegrations } from "@/modules/integrations";
import { useCrmModuleViews, useCrmModuleFields } from "../../hooks/use-campaigns";
import type { CampaignWizardData } from "../../types";

export interface StepCrmSourceProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
    tenantId: string;
}

const SOURCE_TYPES = [
    { value: "manual", label: "Manual Upload", description: "Paste or upload contacts manually" },
    { value: "crm", label: "CRM", description: "Import from your connected CRM" },
    { value: "csv", label: "CSV File", description: "Upload a CSV file with contacts" },
] as const;

const CRM_MODULES = [
    { value: "Leads", label: "Leads" },
    { value: "Contacts", label: "Contacts" },
    { value: "Accounts", label: "Accounts" },
] as const;

export function StepCrmSource({ data, onUpdate, tenantId }: StepCrmSourceProps) {
    const { data: integrationsData } = useCrmIntegrations(tenantId);
    const hasCrmConnected = (integrationsData?.integrations ?? []).some(
        (i) => i.status === "connected"
    );

    const selectedModule = (data.source_config?.module as string) || "";
    const selectedViewId = (data.source_config?.view_id as string) || "";
    const phoneField = (data.source_config?.phone_field as string) || "Phone";

    const { data: viewsData, isLoading: viewsLoading } = useCrmModuleViews(
        selectedModule,
        tenantId
    );
    const { data: fieldsData, isLoading: fieldsLoading } = useCrmModuleFields(
        selectedModule,
        tenantId
    );

    // Filter to fields that could be phone numbers
    const phoneFields = (fieldsData?.fields ?? []).filter(
        (f) =>
            f.data_type === "phone" ||
            f.api_name.toLowerCase().includes("phone") ||
            f.api_name.toLowerCase().includes("mobile") ||
            f.api_name === "Phone" ||
            f.api_name === "Mobile"
    );

    function updateSourceConfig(patch: Record<string, unknown>) {
        onUpdate({
            source_config: { ...data.source_config, ...patch },
        });
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">CRM Source</h2>
                <p className="text-sm text-muted-foreground">
                    Choose where to import contacts from.
                </p>
            </div>

            {/* Source type selection */}
            <div className="grid gap-3">
                {SOURCE_TYPES.map((src) => (
                    <div
                        key={src.value}
                        className={`cursor-pointer rounded-lg border p-4 transition-colors hover:bg-muted/50 ${data.source_type === src.value
                            ? "border-primary ring-1 ring-primary"
                            : ""
                            } ${src.value === "crm" && !hasCrmConnected
                                ? "opacity-50"
                                : ""
                            }`}
                        onClick={() => {
                            if (src.value === "crm" && !hasCrmConnected) return;
                            onUpdate({ source_type: src.value, source_config: {} });
                        }}
                    >
                        <p className="text-sm font-medium">{src.label}</p>
                        <p className="text-xs text-muted-foreground">
                            {src.description}
                        </p>
                        {src.value === "crm" && !hasCrmConnected && (
                            <p className="mt-1 text-xs text-destructive">
                                Connect a CRM in Integrations first.
                            </p>
                        )}
                    </div>
                ))}
            </div>

            {/* Source config — CRM */}
            {data.source_type === "crm" && hasCrmConnected && (
                <div className="space-y-4 rounded-lg border p-4">
                    {/* Module selection */}
                    <div className="space-y-1.5">
                        <Label>CRM Module</Label>
                        <Select
                            value={selectedModule}
                            onValueChange={(v) =>
                                updateSourceConfig({ module: v, view_id: "" })
                            }
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select a module" />
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

                    {/* View / filter selection */}
                    {selectedModule && (
                        <div className="space-y-1.5">
                            <Label>View / Filter</Label>
                            {viewsLoading ? (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    Loading views...
                                </div>
                            ) : (
                                <Select
                                    value={selectedViewId}
                                    onValueChange={(v) =>
                                        updateSourceConfig({ view_id: v })
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="All records (no filter)" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="__all__">
                                            All Records (no filter)
                                        </SelectItem>
                                        {(viewsData?.views ?? []).map((v) => (
                                            <SelectItem key={v.id} value={v.id}>
                                                {v.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            )}
                        </div>
                    )}

                    {/* Phone field selection */}
                    {selectedModule && (
                        <div className="space-y-1.5">
                            <Label>Phone Field</Label>
                            {fieldsLoading ? (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    Loading fields...
                                </div>
                            ) : (
                                <Select
                                    value={phoneField}
                                    onValueChange={(v) =>
                                        updateSourceConfig({ phone_field: v })
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Phone" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {phoneFields.length > 0 ? (
                                            phoneFields.map((f) => (
                                                <SelectItem key={f.api_name} value={f.api_name}>
                                                    {f.display_label} ({f.api_name})
                                                </SelectItem>
                                            ))
                                        ) : (
                                            <>
                                                <SelectItem value="Phone">Phone</SelectItem>
                                                <SelectItem value="Mobile">Mobile</SelectItem>
                                            </>
                                        )}
                                    </SelectContent>
                                </Select>
                            )}
                            <p className="text-xs text-muted-foreground">
                                The CRM field containing the contact&apos;s phone number.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Source config — Manual */}
            {data.source_type === "manual" && (
                <div className="rounded-lg border p-4">
                    <p className="text-sm text-muted-foreground">
                        You can add contacts manually after creating the campaign.
                    </p>
                </div>
            )}

            {/* Source config — CSV */}
            {data.source_type === "csv" && (
                <div className="rounded-lg border p-4 space-y-3">
                    <p className="text-sm font-medium">CSV Upload</p>
                    <p className="text-sm text-muted-foreground">
                        Upload your CSV after creating the campaign. The wizard
                        will save the campaign in draft mode, then you can upload
                        and map columns from the campaign dashboard.
                    </p>
                    <p className="text-xs text-muted-foreground">
                        Required column: <code className="text-xs">phone_number</code> (or any column you map to it).
                        Optional: <code className="text-xs">name</code>,{" "}
                        <code className="text-xs">email</code>,{" "}
                        <code className="text-xs">company</code>.
                        Max 10,000 rows, 10 MB.
                    </p>
                </div>
            )}
        </div>
    );
}
