"use client";

/**
 * CrmSettingsPanel — tenant-level CRM configuration.
 *
 * Lets users configure:
 * 1. Default country code for phone normalization (IN, US, etc.)
 * 2. Auto-create unknown contacts toggle
 * 3. Field mappings: SphereVoice extracted fields → Zoho CRM Contact fields
 */

import { useCallback, useEffect, useState } from "react";
import {
    Globe,
    Loader2,
    MapPin,
    Plus,
    Save,
    Settings2,
    Trash2,
    UserPlus,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { useCrmSettings, useUpdateCrmSettings } from "../hooks/use-crm-data";
import {
    SUPPORTED_COUNTRIES,
    SphereVoice_EXTRACTABLE_FIELDS,
    ZOHO_CONTACT_FIELDS,
} from "../types";

// ── Main Component ──────────────────────────────────────────

export function CrmSettingsPanel({ tenantId }: { tenantId?: string }) {
    const { data: settings, isLoading } = useCrmSettings(tenantId);
    const updateMutation = useUpdateCrmSettings(tenantId);

    // Local state mirrors server state; enables "dirty" detection
    const [defaultCountry, setDefaultCountry] = useState("IN");
    const [autoCreate, setAutoCreate] = useState(false);
    const [mappings, setMappings] = useState<Array<[string, string]>>([]);
    const [isDirty, setIsDirty] = useState(false);

    // Sync local state when server data loads
    useEffect(() => {
        if (settings) {
            setDefaultCountry(settings.default_country || "IN");
            setAutoCreate(settings.auto_create_contact || false);
            const entries = Object.entries(settings.field_mappings || {});
            setMappings(entries.length > 0 ? entries : []);
            setIsDirty(false);
        }
    }, [settings]);

    const markDirty = useCallback(() => setIsDirty(true), []);

    const handleSave = useCallback(async () => {
        const fieldMappingsObj: Record<string, string> = {};
        for (const [SphereVoiceField, zohoField] of mappings) {
            if (SphereVoiceField.trim() && zohoField.trim()) {
                fieldMappingsObj[SphereVoiceField.trim()] = zohoField.trim();
            }
        }

        await updateMutation.mutateAsync({
            default_country: defaultCountry,
            auto_create_contact: autoCreate,
            field_mappings: fieldMappingsObj,
        });
        setIsDirty(false);
    }, [defaultCountry, autoCreate, mappings, updateMutation]);

    const addMapping = useCallback(() => {
        setMappings((prev) => [...prev, ["", ""]]);
        markDirty();
    }, [markDirty]);

    const removeMapping = useCallback(
        (index: number) => {
            setMappings((prev) => prev.filter((_, i) => i !== index));
            markDirty();
        },
        [markDirty]
    );

    const updateMapping = useCallback(
        (index: number, side: 0 | 1, value: string) => {
            setMappings((prev) => {
                const next = [...prev];
                const entry = [...next[index]] as [string, string];
                entry[side] = value;
                next[index] = entry;
                return next;
            });
            markDirty();
        },
        [markDirty]
    );

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* ── Country & Phone Settings ── */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Globe className="h-4 w-4" />
                        Phone &amp; Region Settings
                    </CardTitle>
                    <CardDescription>
                        Controls how phone numbers are normalized when matching callers to
                        CRM contacts. Since we&apos;re focused on Indian calls, &quot;IN&quot; adds +91
                        to bare 10-digit numbers automatically.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid gap-2">
                        <Label htmlFor="default-country">Default Country Code</Label>
                        <Select
                            value={defaultCountry}
                            onValueChange={(v) => {
                                setDefaultCountry(v);
                                markDirty();
                            }}
                        >
                            <SelectTrigger id="default-country" className="w-[280px]">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {Object.entries(SUPPORTED_COUNTRIES).map(([code, label]) => (
                                    <SelectItem key={code} value={code}>
                                        {label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            When a phone number in your CRM doesn&apos;t have a country code (e.g.
                            &quot;9876543210&quot;), we&apos;ll assume this country and prepend the correct
                            code (+91 for India).
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* ── Auto-create contacts ── */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <UserPlus className="h-4 w-4" />
                        Auto-Create Contacts
                    </CardTitle>
                    <CardDescription>
                        When an unknown caller (no match in your CRM) finishes a call and
                        the AI has extracted their name/details, automatically create a new
                        Contact in Zoho CRM.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-3">
                        <Switch
                            checked={autoCreate}
                            onCheckedChange={(checked) => {
                                setAutoCreate(checked);
                                markDirty();
                            }}
                        />
                        <Label className="text-sm">
                            {autoCreate ? "Enabled" : "Disabled"} — new contacts will{" "}
                            {autoCreate ? "" : "not"} be created automatically
                        </Label>
                    </div>
                </CardContent>
            </Card>

            {/* ── Field Mappings ── */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Settings2 className="h-4 w-4" />
                        Field Mappings
                    </CardTitle>
                    <CardDescription>
                        Map the data extracted by the AI during calls to Zoho CRM Contact
                        fields. For example, map &quot;city&quot; → &quot;Mailing_City&quot; so the
                        caller&apos;s city is written to the correct CRM field after the call.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {mappings.length === 0 && (
                        <div className="rounded-lg border border-dashed p-4 text-center">
                            <p className="text-sm text-muted-foreground">
                                No custom field mappings configured. Using system defaults.
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                Add mappings below to customize which extracted fields write to
                                which Zoho CRM fields.
                            </p>
                        </div>
                    )}

                    {mappings.map(([SphereVoiceField, zohoField], index) => (
                        <div key={index} className="flex items-center gap-2">
                            <div className="flex-1">
                                <Select
                                    value={SphereVoiceField}
                                    onValueChange={(v) => updateMapping(index, 0, v)}
                                >
                                    <SelectTrigger className="w-full">
                                        <SelectValue placeholder="SphereVoice extracted field" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SphereVoice_EXTRACTABLE_FIELDS.map((f) => (
                                            <SelectItem key={f.key} value={f.key}>
                                                {f.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <span className="text-sm text-muted-foreground shrink-0">→</span>

                            <div className="flex-1">
                                <Select
                                    value={zohoField}
                                    onValueChange={(v) => updateMapping(index, 1, v)}
                                >
                                    <SelectTrigger className="w-full">
                                        <SelectValue placeholder="Zoho CRM field" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {ZOHO_CONTACT_FIELDS.map((f) => (
                                            <SelectItem key={f} value={f}>
                                                {f.replace(/_/g, " ")}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <Button
                                variant="ghost"
                                size="icon"
                                className="shrink-0"
                                onClick={() => removeMapping(index)}
                            >
                                <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                        </div>
                    ))}

                    <Button variant="outline" size="sm" onClick={addMapping}>
                        <Plus className="h-4 w-4 mr-1" />
                        Add Mapping
                    </Button>
                </CardContent>
            </Card>

            {/* ── Save button ── */}
            <div className="flex items-center justify-between">
                <div>
                    {isDirty && (
                        <Badge variant="secondary" className="text-xs">
                            Unsaved changes
                        </Badge>
                    )}
                    {updateMutation.isError && (
                        <p className="text-sm text-destructive mt-1">
                            {updateMutation.error?.message || "Failed to save"}
                        </p>
                    )}
                    {updateMutation.isSuccess && !isDirty && (
                        <p className="text-sm text-emerald-600 mt-1">Settings saved</p>
                    )}
                </div>
                <Button
                    onClick={handleSave}
                    disabled={!isDirty || updateMutation.isPending}
                >
                    {updateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                        <Save className="h-4 w-4 mr-2" />
                    )}
                    Save Settings
                </Button>
            </div>
        </div>
    );
}
