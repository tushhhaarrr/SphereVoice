"use client";

/**
 * AgentToolsConfig — production tool configuration for AI voice agents.
 *
 * Features:
 * - Dropdowns for calendar, spreadsheet, and sheet tab selection (live from Google APIs)
 * - Column mapping with auto-fetched headers + per-column descriptions
 * - Per-tool usage instructions ("when should the AI use this tool?")
 * - Calendar event duration picker
 * - Sync/refresh button to re-fetch data from Google
 * - Grouped by category with active count badge
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    Calendar,
    Check,
    ChevronDown,
    ExternalLink,
    FileSpreadsheet,
    HelpCircle,
    Link2,
    Loader2,
    Mail,
    MessageSquare,
    Pencil,
    Phone,
    Plus,
    RefreshCw,
    Trash2,
    Users,
    Wrench,
    Zap,
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
import { Textarea } from "@/components/ui/textarea";

import {
    useGoogleCalendarIntegrations,
    useGoogleSheetsIntegrations,
    useInitiateGoogleCalendarOAuth,
    useInitiateGoogleSheetsOAuth,
} from "@/modules/integrations/hooks/use-google-integrations";

import {
    useAgentTools,
    useBindTool,
    useGoogleCalendars,
    useGoogleSheetHeaders,
    useGoogleSheetTabs,
    useGoogleSpreadsheets,
    useTenantTools,
    useUnbindTool,
    type AgentToolBinding,
    type TenantTool,
} from "../hooks/use-tools";

interface AgentToolsConfigProps {
    agentId: string;
    tenantId?: string;
}

/** Column entry stored in AgentTool.config.columns */
interface ColumnEntry {
    name: string;
    description: string;
}

/** The config shape we edit — supports both simple strings and complex values */
type ToolConfig = Record<string, unknown>;

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
    calendar: <Calendar className="h-4 w-4 text-blue-500" />,
    spreadsheet: <FileSpreadsheet className="h-4 w-4 text-green-600" />,
    crm: <Users className="h-4 w-4 text-orange-500" />,
    messaging: <MessageSquare className="h-4 w-4 text-emerald-500" />,
    email: <Mail className="h-4 w-4 text-violet-500" />,
};

const CATEGORY_LABELS: Record<string, string> = {
    calendar: "Google Calendar",
    spreadsheet: "Google Sheets",
    messaging: "Messaging",
    email: "Email",
    crm: "CRM",
    custom: "Custom",
};

/** How the AI uses each tool — shown to the user. */
const TOOL_USAGE_HINTS: Record<string, string> = {
    book_appointment:
        "During a call, when a caller requests an appointment, the AI creates an event on the selected calendar.",
    check_availability:
        "The AI checks the selected calendar for free/busy slots when a caller asks about available times.",
    list_upcoming_events:
        "The AI lists upcoming events from the selected calendar when the caller asks about scheduled appointments.",
    save_to_sheet:
        "After collecting info during a call (e.g. lead details), the AI appends a new row to the selected spreadsheet.",
    read_from_sheet:
        "The AI reads data from the selected spreadsheet during a call (e.g. pricing, FAQs).",
    update_crm_field:
        "During a call, the AI updates a CRM field (e.g. Lead_Status) in real-time when the conversation warrants it.",
    send_whatsapp:
        "During a call, the AI sends a WhatsApp message to the caller (e.g. brochure link, confirmation).",
    send_email:
        "During a call, the AI sends an email to the caller (e.g. follow-up info, booking confirmation).",
};

const DURATION_OPTIONS = [
    { value: "15", label: "15 minutes" },
    { value: "30", label: "30 minutes" },
    { value: "45", label: "45 minutes" },
    { value: "60", label: "1 hour" },
    { value: "90", label: "1.5 hours" },
    { value: "120", label: "2 hours" },
];

/** Extract spreadsheet ID from a full Google Sheets URL or return as-is. */
function normalizeSpreadsheetId(value: string): string {
    const match = value.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : value.trim();
}

// ── Integration connection cards ─────

function ConnectIntegrationCard({
    provider,
    tenantId,
}: {
    provider: "calendar" | "sheets";
    tenantId?: string;
}) {
    const initiateCalendar = useInitiateGoogleCalendarOAuth();
    const initiateSheets = useInitiateGoogleSheetsOAuth();

    const isCalendar = provider === "calendar";
    const initiate = isCalendar ? initiateCalendar : initiateSheets;
    const icon = isCalendar ? (
        <Calendar className="h-5 w-5 text-blue-500" />
    ) : (
        <FileSpreadsheet className="h-5 w-5 text-green-600" />
    );
    const label = isCalendar ? "Google Calendar" : "Google Sheets";
    const description = isCalendar
        ? "Book appointments, check availability, and manage events during calls."
        : "Save caller data, read pricing info, and sync lead details to spreadsheets.";

    return (
        <div className="rounded-lg border-2 border-dashed border-muted-foreground/20 p-4 hover:border-muted-foreground/40 transition-colors">
            <div className="flex items-start gap-3">
                <div className="rounded-md border bg-background p-2 shrink-0">
                    {icon}
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-sm font-medium">{label}</h4>
                        <Button
                            size="sm"
                            variant="default"
                            className="h-7 gap-1.5 px-3 text-xs shrink-0"
                            disabled={initiate.isPending}
                            onClick={() => initiate.mutate({ tenantId })}
                        >
                            {initiate.isPending ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                                <Zap className="h-3 w-3" />
                            )}
                            Connect
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
                </div>
            </div>
        </div>
    );
}

/** Small status pill showing connected account for a category */
function ConnectedAccountBadge({
    email,
    provider,
}: {
    email: string | null;
    provider: string;
}) {
    if (!email) return null;
    const icon =
        provider === "google_calendar" ? (
            <Calendar className="h-3 w-3 text-blue-500" />
        ) : (
            <FileSpreadsheet className="h-3 w-3 text-green-600" />
        );
    return (
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            {icon}
            <span className="truncate max-w-[180px]">{email}</span>
            <div className="h-1.5 w-1.5 rounded-full bg-green-500 shrink-0" />
        </div>
    );
}

// ── Sub-components for config fields ─────

function CalendarConfigFields({
    integrationId,
    tenantId,
    value,
    onChange,
}: {
    integrationId: string | null;
    tenantId?: string;
    value: ToolConfig;
    onChange: (updated: ToolConfig) => void;
}) {
    const { data: calendars, isLoading } = useGoogleCalendars(
        integrationId,
        tenantId
    );

    return (
        <div className="space-y-3">
            {/* Calendar selection */}
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">Which calendar?</Label>
                {isLoading ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Loading your calendars...
                    </div>
                ) : calendars && calendars.length > 0 ? (
                    <Select
                        value={(value.calendar_id as string) || "primary"}
                        onValueChange={(v) => onChange({ ...value, calendar_id: v })}
                    >
                        <SelectTrigger className="h-8 w-full text-xs">
                            <SelectValue placeholder="Select a calendar" />
                        </SelectTrigger>
                        <SelectContent>
                            {calendars.map((cal) => (
                                <SelectItem key={cal.id} value={cal.id}>
                                    <span className="flex items-center gap-2">
                                        {cal.summary || cal.id}
                                        {cal.primary && (
                                            <Badge
                                                variant="secondary"
                                                className="ml-1 text-[10px] px-1 py-0"
                                            >
                                                Primary
                                            </Badge>
                                        )}
                                    </span>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        No calendars found. The default &quot;primary&quot; calendar will be used.
                    </p>
                )}
            </div>

            {/* Event duration */}
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">Default appointment duration</Label>
                <Select
                    value={String(value.event_duration_minutes || "30")}
                    onValueChange={(v) =>
                        onChange({ ...value, event_duration_minutes: parseInt(v, 10) })
                    }
                >
                    <SelectTrigger className="h-8 w-full text-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {DURATION_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p className="text-[11px] text-muted-foreground/70">
                    The AI will use this when creating events if the caller doesn&apos;t specify a length.
                </p>
            </div>

            {/* Tool instructions */}
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">When should the AI use this tool?</Label>
                <Textarea
                    className="min-h-[60px] text-xs resize-none"
                    placeholder="e.g. Book an appointment when the caller asks to schedule a visit or consultation."
                    value={(value.tool_instructions as string) || ""}
                    onChange={(e) =>
                        onChange({ ...value, tool_instructions: e.target.value })
                    }
                />
                <p className="text-[11px] text-muted-foreground/70">
                    This instruction is sent to the AI so it knows when to invoke this tool during calls.
                </p>
            </div>
        </div>
    );
}

function SpreadsheetConfigFields({
    integrationId,
    tenantId,
    toolName,
    value,
    onChange,
}: {
    integrationId: string | null;
    tenantId?: string;
    toolName: string;
    value: ToolConfig;
    onChange: (updated: ToolConfig) => void;
}) {
    const { data: spreadsheets, isLoading: loadingSpreadsheets } =
        useGoogleSpreadsheets(integrationId, tenantId);

    const selectedSpreadsheetId = value.spreadsheet_id
        ? normalizeSpreadsheetId(value.spreadsheet_id as string)
        : undefined;

    const { data: tabs, isLoading: loadingTabs } = useGoogleSheetTabs(
        integrationId,
        selectedSpreadsheetId,
        tenantId
    );

    const sheetName = (value.sheet_name as string) || undefined;

    const {
        data: fetchedHeaders,
        isLoading: loadingHeaders,
        refetch: refetchHeaders,
        isFetching: fetchingHeaders,
    } = useGoogleSheetHeaders(
        integrationId,
        selectedSpreadsheetId,
        sheetName,
        tenantId
    );

    const columns: ColumnEntry[] = (value.columns as ColumnEntry[]) || [];
    const isSaveType = toolName === "save_to_sheet";

    // When headers are fetched, merge them into existing columns
    // (preserve descriptions for matching names, add new ones, drop removed ones)
    const handleSyncHeaders = useCallback(() => {
        refetchHeaders().then((result) => {
            const headers = result.data;
            if (!headers || headers.length === 0) return;

            const existingByName = new Map(
                columns.map((c) => [c.name, c.description])
            );
            const merged: ColumnEntry[] = headers.map((h) => ({
                name: h,
                description: existingByName.get(h) || "",
            }));
            onChange({ ...value, columns: merged });
        });
    }, [refetchHeaders, columns, onChange, value]);

    // Auto-sync headers when a sheet tab is first selected and no columns exist
    useEffect(() => {
        if (fetchedHeaders && fetchedHeaders.length > 0 && columns.length === 0 && isSaveType) {
            const initial: ColumnEntry[] = fetchedHeaders.map((h) => ({
                name: h,
                description: "",
            }));
            onChange({ ...value, columns: initial });
        }
        // Only on header data arrival when columns are empty
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fetchedHeaders]);

    const updateColumnDescription = useCallback(
        (index: number, description: string) => {
            const updated = [...columns];
            updated[index] = { ...updated[index], description };
            onChange({ ...value, columns: updated });
        },
        [columns, onChange, value]
    );

    return (
        <div className="space-y-3">
            {/* Spreadsheet picker */}
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">Which spreadsheet?</Label>
                {loadingSpreadsheets ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Loading your spreadsheets...
                    </div>
                ) : spreadsheets && spreadsheets.length > 0 ? (
                    <>
                        <Select
                            value={selectedSpreadsheetId || ""}
                            onValueChange={(v) => {
                                const name = spreadsheets?.find((s) => s.id === v)?.name || "";
                                onChange({ ...value, spreadsheet_id: v, spreadsheet_name: name, sheet_name: "", columns: [] });
                            }}
                        >
                            <SelectTrigger className="h-8 w-full text-xs">
                                <SelectValue placeholder="Select a spreadsheet" />
                            </SelectTrigger>
                            <SelectContent>
                                {spreadsheets.map((ss) => (
                                    <SelectItem key={ss.id} value={ss.id}>
                                        <span className="flex items-center gap-2">
                                            <FileSpreadsheet className="h-3 w-3 text-green-600 shrink-0" />
                                            {ss.name}
                                        </span>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {selectedSpreadsheetId && (
                            <p className="text-[10px] text-muted-foreground/60 font-mono truncate">
                                ID: {selectedSpreadsheetId}
                            </p>
                        )}
                    </>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        No spreadsheets found in this Google account.
                    </p>
                )}
            </div>

            {/* Sheet tab picker */}
            {selectedSpreadsheetId && (
                <div className="space-y-1.5">
                    <Label className="text-xs font-medium">Which sheet tab?</Label>
                    {loadingTabs ? (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Loading tabs...
                        </div>
                    ) : tabs && tabs.length > 0 ? (
                        <Select
                            value={(value.sheet_name as string) || ""}
                            onValueChange={(v) => onChange({ ...value, sheet_name: v, columns: [] })}
                        >
                            <SelectTrigger className="h-8 w-full text-xs">
                                <SelectValue placeholder="Select a tab" />
                            </SelectTrigger>
                            <SelectContent>
                                {tabs.map((tab) => (
                                    <SelectItem key={tab.sheet_id} value={tab.title}>
                                        {tab.title}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    ) : (
                        <p className="text-xs text-muted-foreground">
                            No tabs found. &quot;Sheet1&quot; will be used as default.
                        </p>
                    )}
                </div>
            )}

            {/* Column mapping — only for save_to_sheet */}
            {isSaveType && sheetName && selectedSpreadsheetId && (
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs font-medium">
                            Column mapping
                            {columns.length > 0 && (
                                <span className="ml-1 text-muted-foreground font-normal">
                                    ({columns.length} fields)
                                </span>
                            )}
                        </Label>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 gap-1 px-2 text-[11px]"
                            disabled={fetchingHeaders}
                            onClick={handleSyncHeaders}
                        >
                            <RefreshCw
                                className={`h-3 w-3 ${fetchingHeaders ? "animate-spin" : ""}`}
                            />
                            Sync Headers
                        </Button>
                    </div>

                    {loadingHeaders && columns.length === 0 ? (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Reading column headers from your sheet...
                        </div>
                    ) : columns.length > 0 ? (
                        <div className="space-y-1.5 rounded-md border bg-muted/20 p-2">
                            {columns.map((col, i) => (
                                <div key={col.name} className="flex items-start gap-2">
                                    <div className="flex h-7 min-w-[100px] max-w-[140px] items-center rounded bg-muted px-2">
                                        <span className="truncate text-xs font-medium">
                                            {col.name}
                                        </span>
                                    </div>
                                    <Input
                                        className="h-7 flex-1 text-xs"
                                        placeholder={`What goes in "${col.name}"?`}
                                        value={col.description}
                                        onChange={(e) => updateColumnDescription(i, e.target.value)}
                                    />
                                </div>
                            ))}
                            <p className="text-[10px] text-muted-foreground/70 pt-1">
                                Describe each column so the AI knows what data to collect during calls.
                                The AI will fill these fields based on the conversation.
                            </p>
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground">
                            No headers found. Add column headers to row 1 of your sheet, then click
                            &quot;Sync Headers&quot;.
                        </p>
                    )}
                </div>
            )}

            {/* Tool instructions */}
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">When should the AI use this tool?</Label>
                <Textarea
                    className="min-h-[60px] text-xs resize-none"
                    placeholder={
                        isSaveType
                            ? "e.g. Save the caller's details after collecting their name and phone number."
                            : "e.g. Look up the caller's order status when they provide an order number."
                    }
                    value={(value.tool_instructions as string) || ""}
                    onChange={(e) =>
                        onChange({ ...value, tool_instructions: e.target.value })
                    }
                />
                <p className="text-[11px] text-muted-foreground/70">
                    This instruction tells the AI exactly when to invoke this tool during calls.
                </p>
            </div>
        </div>
    );
}

// ── CRM Write config fields ─────

function CrmWriteConfigFields({
    value,
    onChange,
}: {
    value: ToolConfig;
    onChange: (v: ToolConfig) => void;
}) {
    const rawAllowed = (value.allowed_fields as string) || "";
    return (
        <div className="space-y-3">
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">Allowed CRM Fields</Label>
                <Textarea
                    className="min-h-[60px] text-xs resize-none font-mono"
                    placeholder="Lead_Status&#10;Description&#10;Rating"
                    value={rawAllowed}
                    onChange={(e) =>
                        onChange({ ...value, allowed_fields: e.target.value })
                    }
                />
                <p className="text-[11px] text-muted-foreground/70">
                    One field name per line. The AI can only update these CRM fields during calls.
                    Leave empty to allow any field (not recommended).
                </p>
            </div>
            <div className="space-y-1.5">
                <Label className="text-xs font-medium">When should the AI use this tool?</Label>
                <Textarea
                    className="min-h-[60px] text-xs resize-none"
                    placeholder="e.g. Update the lead status when the caller confirms interest or disinterest."
                    value={(value.tool_instructions as string) || ""}
                    onChange={(e) =>
                        onChange({ ...value, tool_instructions: e.target.value })
                    }
                />
            </div>
        </div>
    );
}

// ── Main component ─────

export function AgentToolsConfig({ agentId, tenantId }: AgentToolsConfigProps) {
    const { data: tenantToolsData, isLoading: loadingTenantTools } =
        useTenantTools(tenantId);
    const { data: agentToolBindings, isLoading: loadingAgentTools } =
        useAgentTools(agentId, tenantId);
    const bindTool = useBindTool(agentId, tenantId);
    const unbindTool = useUnbindTool(agentId, tenantId);

    // Check which integrations are connected
    const { data: calendarIntegrations, isLoading: loadingCalIntegrations } =
        useGoogleCalendarIntegrations(tenantId);
    const { data: sheetsIntegrations, isLoading: loadingSheetsIntegrations } =
        useGoogleSheetsIntegrations(tenantId);

    const calendarConnected =
        (calendarIntegrations?.integrations ?? []).some(
            (i) => i.status === "connected"
        );
    const sheetsConnected =
        (sheetsIntegrations?.integrations ?? []).some(
            (i) => i.status === "connected"
        );
    const calendarEmail =
        calendarIntegrations?.integrations?.find((i) => i.status === "connected")
            ?.account_email ?? null;
    const sheetsEmail =
        sheetsIntegrations?.integrations?.find((i) => i.status === "connected")
            ?.account_email ?? null;

    const [editingConfig, setEditingConfig] = useState<
        Record<string, ToolConfig>
    >({});
    const [expandedToolId, setExpandedToolId] = useState<string | null>(null);
    const [showHowItWorks, setShowHowItWorks] = useState(false);

    const allTools = tenantToolsData?.items ?? [];
    const bindingsByToolId = useMemo(
        () =>
            (agentToolBindings ?? []).reduce<Record<string, AgentToolBinding>>(
                (acc, b) => {
                    acc[b.tool_id] = b;
                    return acc;
                },
                {}
            ),
        [agentToolBindings]
    );

    const isLoading = loadingTenantTools || loadingAgentTools || loadingCalIntegrations || loadingSheetsIntegrations;

    // Find integration IDs by category so we can call Google APIs
    const integrationIdByCategory = useMemo(() => {
        const map: Record<string, string | null> = {};
        for (const tool of allTools) {
            if (tool.integration_id && !map[tool.category]) {
                map[tool.category] = tool.integration_id;
            }
        }
        return map;
    }, [allTools]);

    const handleEnableTool = useCallback(
        (tool: TenantTool) => {
            const needsConfig =
                tool.category === "calendar" || tool.category === "spreadsheet";
            if (needsConfig) {
                const defaults: ToolConfig =
                    tool.category === "calendar"
                        ? { calendar_id: "primary", event_duration_minutes: 30, tool_instructions: "" }
                        : { spreadsheet_id: "", spreadsheet_name: "", sheet_name: "", columns: [], tool_instructions: "" };
                setEditingConfig((prev) => ({ ...prev, [tool.id]: defaults }));
                setExpandedToolId(tool.id);
            } else {
                bindTool.mutate({ toolId: tool.id });
            }
        },
        [bindTool]
    );

    const handleSaveConfig = useCallback(
        (toolId: string) => {
            const raw = editingConfig[toolId] || {};
            const config: Record<string, unknown> = {};

            for (const [k, v] of Object.entries(raw)) {
                // Normalise spreadsheet ID
                if (k === "spreadsheet_id" && typeof v === "string" && v) {
                    config[k] = normalizeSpreadsheetId(v);
                }
                // Keep arrays/objects (columns) as-is
                else if (Array.isArray(v)) {
                    if (v.length > 0) config[k] = v;
                }
                // Keep numbers as-is
                else if (typeof v === "number") {
                    config[k] = v;
                }
                // Remove empty strings
                else if (typeof v === "string" && v.trim()) {
                    config[k] = v;
                }
                // Keep other truthy values
                else if (v !== "" && v !== null && v !== undefined) {
                    config[k] = v;
                }
            }

            bindTool.mutate(
                { toolId, config },
                {
                    onSuccess: () => {
                        setExpandedToolId(null);
                        setEditingConfig((prev) => {
                            const next = { ...prev };
                            delete next[toolId];
                            return next;
                        });
                    },
                }
            );
        },
        [bindTool, editingConfig]
    );

    const handleEditConfig = useCallback(
        (tool: TenantTool, binding: AgentToolBinding) => {
            const cfg = binding.config || {};
            const existingConfig: ToolConfig = {};
            if (tool.category === "calendar") {
                existingConfig.calendar_id =
                    (cfg.calendar_id as string) || "primary";
                existingConfig.event_duration_minutes =
                    (cfg.event_duration_minutes as number) || 30;
                existingConfig.tool_instructions =
                    (cfg.tool_instructions as string) || "";
            } else if (tool.category === "spreadsheet") {
                existingConfig.spreadsheet_id =
                    (cfg.spreadsheet_id as string) || "";
                existingConfig.spreadsheet_name =
                    (cfg.spreadsheet_name as string) || "";
                existingConfig.sheet_name =
                    (cfg.sheet_name as string) || "";
                existingConfig.columns =
                    (cfg.columns as ColumnEntry[]) || [];
                existingConfig.tool_instructions =
                    (cfg.tool_instructions as string) || "";
            }
            setEditingConfig((prev) => ({ ...prev, [tool.id]: existingConfig }));
            setExpandedToolId(tool.id);
        },
        []
    );

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading tools…
            </div>
        );
    }

    if (allTools.length === 0) {
        // No tools exist yet — show connect cards for all unconnected integrations
        const needsCalendar = !calendarConnected;
        const needsSheets = !sheetsConnected;

        return (
            <div className="space-y-4">
                <div>
                    <h3 className="text-sm font-medium">Integration Tools</h3>
                    <p className="text-xs text-muted-foreground">
                        Connect a Google service to unlock AI tools for this agent.
                    </p>
                </div>

                <div className="grid gap-2">
                    {needsSheets && (
                        <ConnectIntegrationCard provider="sheets" tenantId={tenantId} />
                    )}
                    {needsCalendar && (
                        <ConnectIntegrationCard provider="calendar" tenantId={tenantId} />
                    )}
                    {!needsCalendar && !needsSheets && (
                        <div className="rounded-lg border border-dashed p-6 text-center">
                            <Wrench className="mx-auto mb-2 h-8 w-8 text-muted-foreground/60" />
                            <p className="text-sm font-medium text-muted-foreground">
                                Integrations connected — tools loading...
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground/80">
                                Try refreshing the page. Tools should appear automatically after connecting.
                            </p>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Group tools by category
    const grouped = allTools.reduce<Record<string, TenantTool[]>>(
        (acc, tool) => {
            const cat = tool.category;
            if (!acc[cat]) acc[cat] = [];
            acc[cat].push(tool);
            return acc;
        },
        {}
    );

    const enabledCount = Object.keys(bindingsByToolId).length;

    return (
        <div className="space-y-4">
            {/* Header */}
            <div>
                <h3 className="text-sm font-medium">Integration Tools</h3>
                <p className="text-xs text-muted-foreground">
                    Connect services and enable tools so the AI can take actions during calls.
                    {enabledCount > 0 && (
                        <span className="ml-1 text-primary font-medium">
                            {enabledCount} active
                        </span>
                    )}
                </p>
            </div>

            {/* How it works */}
            <div>
                <button
                    type="button"
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => setShowHowItWorks((v) => !v)}
                >
                    <HelpCircle className="h-3.5 w-3.5" />
                    How do tools work during calls?
                    <ChevronDown
                        className={`h-3 w-3 transition-transform ${showHowItWorks ? "rotate-180" : ""
                            }`}
                    />
                </button>
                {showHowItWorks && (
                    <div className="mt-2 rounded-lg border bg-muted/30 p-3 space-y-2">
                        <div className="flex items-start gap-2">
                            <Phone className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                            <div className="text-xs space-y-1.5">
                                <p>
                                    <span className="font-medium">When a call starts</span>, the
                                    AI loads all enabled tools for this agent. Each tool becomes an
                                    action the AI can take based on the conversation.
                                </p>
                                <p>
                                    <span className="font-medium">During the call</span>, if the
                                    caller says something that matches a tool&apos;s purpose (like
                                    &quot;I want to book an appointment&quot;), the AI
                                    automatically invokes the tool with the right parameters.
                                </p>
                                <p>
                                    <span className="font-medium">The config you set below</span>{" "}
                                    (which calendar, which spreadsheet) tells the tool{" "}
                                    <em>where</em> to act. Different agents can use different
                                    calendars or spreadsheets.
                                </p>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Tool groups */}
            {Object.entries(grouped).map(([category, tools]) => {
                const email = category === "calendar" ? calendarEmail : sheetsEmail;
                const provider = category === "calendar" ? "google_calendar" : "google_sheets";
                return (
                    <div key={category} className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                {CATEGORY_ICONS[category] ?? <Wrench className="h-3.5 w-3.5" />}
                                {CATEGORY_LABELS[category] ?? category}
                            </div>
                            <ConnectedAccountBadge email={email} provider={provider} />
                        </div>

                        <div className="grid gap-2">
                            {tools.map((tool) => {
                                const binding = bindingsByToolId[tool.id];
                                const isBound = !!binding;
                                const isExpanded = expandedToolId === tool.id;
                                const isPending = bindTool.isPending || unbindTool.isPending;
                                const usageHint = TOOL_USAGE_HINTS[tool.name];
                                const integrationId =
                                    integrationIdByCategory[tool.category] ?? null;

                                return (
                                    <Card
                                        key={tool.id}
                                        className={`transition-colors ${isBound
                                            ? "border-primary/30 bg-primary/5"
                                            : "border-border"
                                            }`}
                                    >
                                        <CardHeader className="p-3 pb-1">
                                            <div className="flex items-center justify-between">
                                                <div className="flex-1 min-w-0">
                                                    <CardTitle className="text-sm font-medium">
                                                        {tool.display_name}
                                                    </CardTitle>
                                                </div>
                                                <div className="flex items-center gap-2 shrink-0">
                                                    {isBound && (
                                                        <Badge
                                                            variant="default"
                                                            className="bg-green-600 text-xs hover:bg-green-600"
                                                        >
                                                            Active
                                                        </Badge>
                                                    )}
                                                    {isBound ? (
                                                        <div className="flex items-center gap-1">
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-7 px-2"
                                                                disabled={isPending}
                                                                onClick={() =>
                                                                    handleEditConfig(tool, binding)
                                                                }
                                                            >
                                                                <Pencil className="h-3.5 w-3.5" />
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-7 px-2 text-destructive hover:text-destructive"
                                                                disabled={isPending}
                                                                onClick={() =>
                                                                    unbindTool.mutate({ toolId: tool.id })
                                                                }
                                                            >
                                                                {unbindTool.isPending ? (
                                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                                ) : (
                                                                    <Trash2 className="h-3.5 w-3.5" />
                                                                )}
                                                            </Button>
                                                        </div>
                                                    ) : (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            className="h-7 gap-1 px-2 text-xs"
                                                            disabled={isPending}
                                                            onClick={() => handleEnableTool(tool)}
                                                        >
                                                            {bindTool.isPending ? (
                                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                            ) : (
                                                                <>
                                                                    <Plus className="h-3 w-3" />
                                                                    Enable
                                                                </>
                                                            )}
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="px-3 pb-3 pt-0">
                                            <CardDescription className="text-xs">
                                                {tool.description}
                                            </CardDescription>

                                            {/* Usage hint */}
                                            {usageHint && (
                                                <p className="mt-1.5 text-[11px] text-blue-600/80 dark:text-blue-400/80 italic">
                                                    {usageHint}
                                                </p>
                                            )}

                                            {/* Config summary when bound & not editing */}
                                            {isBound && !isExpanded && (
                                                <ConfigSummary tool={tool} binding={binding} />
                                            )}

                                            {/* Inline config — Calendar */}
                                            {isExpanded && tool.category === "calendar" && (
                                                <div className="mt-3 space-y-3 rounded-md border bg-background p-3">
                                                    <CalendarConfigFields
                                                        integrationId={integrationId}
                                                        tenantId={tenantId}
                                                        value={editingConfig[tool.id] ?? {}}
                                                        onChange={(v) =>
                                                            setEditingConfig((prev) => ({
                                                                ...prev,
                                                                [tool.id]: v,
                                                            }))
                                                        }
                                                    />
                                                    <ConfigFormActions
                                                        isBound={isBound}
                                                        isPending={isPending}
                                                        isBindPending={bindTool.isPending}
                                                        onSave={() => handleSaveConfig(tool.id)}
                                                        onCancel={() => {
                                                            setExpandedToolId(null);
                                                            setEditingConfig((prev) => {
                                                                const next = { ...prev };
                                                                delete next[tool.id];
                                                                return next;
                                                            });
                                                        }}
                                                    />
                                                </div>
                                            )}

                                            {/* Inline config — Spreadsheet */}
                                            {isExpanded && tool.category === "spreadsheet" && (
                                                <div className="mt-3 space-y-3 rounded-md border bg-background p-3">
                                                    <SpreadsheetConfigFields
                                                        integrationId={integrationId}
                                                        tenantId={tenantId}
                                                        toolName={tool.name}
                                                        value={editingConfig[tool.id] ?? {}}
                                                        onChange={(v) =>
                                                            setEditingConfig((prev) => ({
                                                                ...prev,
                                                                [tool.id]: v,
                                                            }))
                                                        }
                                                    />
                                                    <ConfigFormActions
                                                        isBound={isBound}
                                                        isPending={isPending}
                                                        isBindPending={bindTool.isPending}
                                                        onSave={() => handleSaveConfig(tool.id)}
                                                        onCancel={() => {
                                                            setExpandedToolId(null);
                                                            setEditingConfig((prev) => {
                                                                const next = { ...prev };
                                                                delete next[tool.id];
                                                                return next;
                                                            });
                                                        }}
                                                    />
                                                </div>
                                            )}

                                            {/* Inline config — CRM Write */}
                                            {isExpanded && tool.category === "crm" && (
                                                <div className="mt-3 space-y-3 rounded-md border bg-background p-3">
                                                    <CrmWriteConfigFields
                                                        value={editingConfig[tool.id] ?? {}}
                                                        onChange={(v) =>
                                                            setEditingConfig((prev) => ({
                                                                ...prev,
                                                                [tool.id]: v,
                                                            }))
                                                        }
                                                    />
                                                    <ConfigFormActions
                                                        isBound={isBound}
                                                        isPending={isPending}
                                                        isBindPending={bindTool.isPending}
                                                        onSave={() => handleSaveConfig(tool.id)}
                                                        onCancel={() => {
                                                            setExpandedToolId(null);
                                                            setEditingConfig((prev) => {
                                                                const next = { ...prev };
                                                                delete next[tool.id];
                                                                return next;
                                                            });
                                                        }}
                                                    />
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </div>
                );
            })}

            {/* Connect more integrations — show for any unconnected service */}
            {(() => {
                const needsCalendar = !calendarConnected;
                const needsSheets = !sheetsConnected;
                if (!needsCalendar && !needsSheets) return null;
                const nothingConnected = needsCalendar && needsSheets;
                return (
                    <div className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            <Link2 className="h-3.5 w-3.5" />
                            {nothingConnected ? "Connect an Integration" : "Add Another Integration"}
                        </div>
                        <div className="grid gap-2">
                            {needsSheets && (
                                <ConnectIntegrationCard provider="sheets" tenantId={tenantId} />
                            )}
                            {needsCalendar && (
                                <ConnectIntegrationCard provider="calendar" tenantId={tenantId} />
                            )}
                        </div>
                    </div>
                );
            })()}

            {(bindTool.isError || unbindTool.isError) && (
                <p className="text-xs text-destructive">
                    {bindTool.error?.message || unbindTool.error?.message}
                </p>
            )}
        </div>
    );
}

// ── Config Summary ─────

function ConfigSummary({
    tool,
    binding,
}: {
    tool: TenantTool;
    binding: AgentToolBinding;
}) {
    const config = binding.config;
    if (!config || Object.keys(config).length === 0) return null;

    const instructions = config.tool_instructions as string | undefined;

    if (tool.category === "calendar") {
        const calId = config.calendar_id as string | undefined;
        const duration = config.event_duration_minutes as number | undefined;
        return (
            <div className="mt-2 space-y-1 text-[11px] text-muted-foreground">
                <div className="flex items-center gap-2">
                    <Calendar className="h-3 w-3" />
                    <span>
                        Calendar:{" "}
                        <span className="font-medium">
                            {calId === "primary"
                                ? "Primary calendar"
                                : calId || "Primary calendar"}
                        </span>
                        {duration && (
                            <span className="ml-2 text-muted-foreground/70">
                                {duration} min appointments
                            </span>
                        )}
                    </span>
                </div>
                {instructions && (
                    <p className="ml-5 italic text-muted-foreground/70 truncate">
                        When: {instructions}
                    </p>
                )}
            </div>
        );
    }

    if (tool.category === "spreadsheet") {
        const ssId = config.spreadsheet_id as string | undefined;
        const ssName = config.spreadsheet_name as string | undefined;
        const sheetName = config.sheet_name as string | undefined;
        const columns = config.columns as ColumnEntry[] | undefined;
        return (
            <div className="mt-2 flex flex-col gap-1 text-[11px] text-muted-foreground">
                <div className="flex items-center gap-2">
                    <FileSpreadsheet className="h-3 w-3" />
                    <span>
                        {ssName ? (
                            <>
                                <span className="font-medium">{ssName}</span>
                                {sheetName && (
                                    <span className="text-muted-foreground/70"> / {sheetName}</span>
                                )}
                            </>
                        ) : ssId ? (
                            <span className="font-medium font-mono">
                                {ssId.length > 20
                                    ? ssId.slice(0, 10) + "\u2026" + ssId.slice(-6)
                                    : ssId}
                            </span>
                        ) : (
                            "Not configured"
                        )}
                    </span>
                    {ssId && (
                        <a
                            href={"https://docs.google.com/spreadsheets/d/" + ssId + "/edit"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                        >
                            <ExternalLink className="h-3 w-3" />
                        </a>
                    )}
                </div>
                {columns && columns.length > 0 && (
                    <div className="ml-5 flex flex-wrap gap-1">
                        {columns.map((col) => (
                            <Badge
                                key={col.name}
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0 font-normal"
                            >
                                {col.name}
                            </Badge>
                        ))}
                    </div>
                )}
                {instructions && (
                    <p className="ml-5 italic text-muted-foreground/70 truncate">
                        When: {instructions}
                    </p>
                )}
            </div>
        );
    }

    return null;
}

// ── Config form save/cancel buttons ─────

function ConfigFormActions({
    isBound,
    isPending,
    isBindPending,
    onSave,
    onCancel,
}: {
    isBound: boolean;
    isPending: boolean;
    isBindPending: boolean;
    onSave: () => void;
    onCancel: () => void;
}) {
    return (
        <div className="flex items-center gap-2 pt-1">
            <Button
                size="sm"
                className="h-7 gap-1 text-xs"
                disabled={isPending}
                onClick={onSave}
            >
                {isBindPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                    <Check className="h-3 w-3" />
                )}
                {isBound ? "Update" : "Enable"}
            </Button>
            <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={onCancel}
            >
                Cancel
            </Button>
        </div>
    );
}
