"use client";

/**
 * FunctionCallingConfig — UI for defining callable functions on an agent.
 *
 * Allows users to:
 * - Add/edit/remove custom functions (name, description, parameters, endpoint)
 * - Built-in functions (end_call, transfer_call) are shown as non-removable
 * - Each function has: name, description, parameters (name, type, required), endpoint URL
 *
 * The config maps to the `config.functions` array in the agent JSONB.
 */

import { useCallback, useMemo, useState } from "react";
import {
    Plus,
    Trash2,
    ChevronDown,
    ChevronRight,
    GripVertical,
    Zap,
    Globe,
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
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

// ── Types ───────────────────────────────────────────────────

export interface FunctionParameter {
    name: string;
    type: "string" | "number" | "boolean" | "object" | "array";
    description: string;
    required: boolean;
}

export interface AgentFunction {
    /** Unique name used in tool_call — must be lowercase + underscore */
    name: string;
    /** Human-readable description shown to the LLM */
    description: string;
    /** Function parameters schema */
    parameters: FunctionParameter[];
    /** Webhook URL to call when function is invoked (custom functions only) */
    webhookUrl: string;
    /** HTTP method for the webhook */
    webhookMethod: "GET" | "POST" | "PUT";
    /** Whether this is a built-in function (cannot be deleted) */
    isBuiltin: boolean;
    /** Whether this function is enabled */
    enabled: boolean;
}

interface FunctionCallingConfigProps {
    functions: AgentFunction[];
    onChange: (functions: AgentFunction[]) => void;
    readOnly?: boolean;
}

// ── Built-in Functions ──────────────────────────────────────

const BUILTIN_FUNCTIONS: AgentFunction[] = [
    {
        name: "end_call",
        description: "End the current call. Use when the conversation is complete or the user requests to hang up.",
        parameters: [
            {
                name: "reason",
                type: "string",
                description: "Reason for ending the call (e.g. 'conversation_complete', 'user_requested')",
                required: false,
            },
        ],
        webhookUrl: "",
        webhookMethod: "POST",
        isBuiltin: true,
        enabled: true,
    },
    {
        name: "transfer_call",
        description: "Transfer the call to a human agent or another phone number.",
        parameters: [
            {
                name: "phone_number",
                type: "string",
                description: "The phone number to transfer the call to (E.164 format)",
                required: true,
            },
            {
                name: "reason",
                type: "string",
                description: "Reason for the transfer",
                required: false,
            },
        ],
        webhookUrl: "",
        webhookMethod: "POST",
        isBuiltin: true,
        enabled: true,
    },
];

// ── Helpers ─────────────────────────────────────────────────

function createEmptyFunction(): AgentFunction {
    return {
        name: "",
        description: "",
        parameters: [],
        webhookUrl: "",
        webhookMethod: "POST",
        isBuiltin: false,
        enabled: true,
    };
}

function createEmptyParameter(): FunctionParameter {
    return {
        name: "",
        type: "string",
        description: "",
        required: false,
    };
}

// ── Main Component ──────────────────────────────────────────

export function FunctionCallingConfig({
    functions,
    onChange,
    readOnly = false,
}: FunctionCallingConfigProps) {
    const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

    // Ensure built-in functions are always present
    const allFunctions = useMemo(
        () => [
            ...BUILTIN_FUNCTIONS.map((builtin) => {
                const existing = functions.find((f) => f.name === builtin.name);
                return existing ? { ...builtin, enabled: existing.enabled } : builtin;
            }),
            ...functions.filter((f) => !f.isBuiltin),
        ],
        [functions]
    );

    const handleToggle = useCallback(
        (index: number) => {
            setExpandedIndex((prev) => (prev === index ? null : index));
        },
        []
    );

    const handleAddFunction = useCallback(() => {
        const newFn = createEmptyFunction();
        const updated = [...functions.filter((f) => !f.isBuiltin), newFn];
        // Reconstruct: keep builtins from current + new customs
        const builtinState = functions.filter((f) => f.isBuiltin);
        onChange([...builtinState, ...updated]);
        setExpandedIndex(BUILTIN_FUNCTIONS.length + updated.length - 1);
    }, [functions, onChange]);

    const handleRemoveFunction = useCallback(
        (index: number) => {
            // Offset by builtin count to get the custom function index
            const customIndex = index - BUILTIN_FUNCTIONS.length;
            const customs = functions.filter((f) => !f.isBuiltin);
            customs.splice(customIndex, 1);
            const builtinState = functions.filter((f) => f.isBuiltin);
            onChange([...builtinState, ...customs]);
            setExpandedIndex(null);
        },
        [functions, onChange]
    );

    const handleUpdateFunction = useCallback(
        (index: number, updated: AgentFunction) => {
            const newAll = [...allFunctions];
            newAll[index] = updated;
            onChange(newAll);
        },
        [allFunctions, onChange]
    );

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-sm font-medium flex items-center gap-1.5">
                            <Zap className="h-4 w-4" />
                            Functions
                        </CardTitle>
                        <CardDescription className="text-xs">
                            Define functions the AI agent can call during conversation
                        </CardDescription>
                    </div>
                    {!readOnly && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleAddFunction}
                            className="gap-1"
                        >
                            <Plus className="h-3.5 w-3.5" />
                            Add Function
                        </Button>
                    )}
                </div>
            </CardHeader>

            <Separator />

            <CardContent className="pt-3">
                <div className="space-y-2">
                    {allFunctions.map((fn, index) => (
                        <FunctionItem
                            key={`${fn.name}-${index}`}
                            func={fn}
                            index={index}
                            isExpanded={expandedIndex === index}
                            onToggle={handleToggle}
                            onUpdate={handleUpdateFunction}
                            onRemove={handleRemoveFunction}
                            readOnly={readOnly}
                        />
                    ))}

                    {allFunctions.length === 0 && (
                        <div className="py-4 text-center text-sm text-muted-foreground">
                            No functions configured. Add a function to enable tool calling.
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

// ── Function Item (collapsible) ─────────────────────────────

interface FunctionItemProps {
    func: AgentFunction;
    index: number;
    isExpanded: boolean;
    onToggle: (index: number) => void;
    onUpdate: (index: number, fn: AgentFunction) => void;
    onRemove: (index: number) => void;
    readOnly: boolean;
}

function FunctionItem({
    func,
    index,
    isExpanded,
    onToggle,
    onUpdate,
    onRemove,
    readOnly,
}: FunctionItemProps) {
    const handleFieldChange = useCallback(
        <K extends keyof AgentFunction>(field: K, value: AgentFunction[K]) => {
            onUpdate(index, { ...func, [field]: value });
        },
        [func, index, onUpdate]
    );

    const handleAddParam = useCallback(() => {
        onUpdate(index, {
            ...func,
            parameters: [...func.parameters, createEmptyParameter()],
        });
    }, [func, index, onUpdate]);

    const handleRemoveParam = useCallback(
        (paramIndex: number) => {
            const newParams = [...func.parameters];
            newParams.splice(paramIndex, 1);
            onUpdate(index, { ...func, parameters: newParams });
        },
        [func, index, onUpdate]
    );

    const handleUpdateParam = useCallback(
        (paramIndex: number, updated: FunctionParameter) => {
            const newParams = [...func.parameters];
            newParams[paramIndex] = updated;
            onUpdate(index, { ...func, parameters: newParams });
        },
        [func, index, onUpdate]
    );

    return (
        <div className="rounded-md border">
            {/* Header */}
            <div className="flex items-center gap-2 px-3 py-2.5 hover:bg-muted/50 transition-colors">
                <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    onClick={() => onToggle(index)}
                    aria-expanded={isExpanded}
                >
                    <GripVertical className="h-3.5 w-3.5 text-muted-foreground/50" />
                    {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    <span className="truncate font-mono text-sm font-medium">
                        {func.name || "unnamed_function"}
                    </span>
                    {func.isBuiltin && (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            Built-in
                        </Badge>
                    )}
                    {!func.isBuiltin && func.webhookUrl && (
                        <Globe className="h-3 w-3 shrink-0 text-muted-foreground" />
                    )}
                </button>
                <div className="ml-auto flex shrink-0 items-center gap-2">
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                        {func.parameters.length} param{func.parameters.length !== 1 ? "s" : ""}
                    </Badge>
                    <Switch
                        checked={func.enabled}
                        onCheckedChange={(val) => handleFieldChange("enabled", val)}
                        disabled={readOnly}
                        className="scale-75"
                    />
                </div>
            </div>

            {/* Expanded content */}
            {isExpanded && (
                <div className="space-y-3 border-t px-3 py-3">
                    {/* Name + Description */}
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <Label className="text-xs">Function Name</Label>
                            <Input
                                value={func.name}
                                onChange={(e) => handleFieldChange("name", e.target.value)}
                                placeholder="my_function"
                                disabled={readOnly || func.isBuiltin}
                                className="font-mono text-sm h-8"
                            />
                        </div>
                        <div>
                            <Label className="text-xs">Webhook URL</Label>
                            <Input
                                value={func.webhookUrl}
                                onChange={(e) => handleFieldChange("webhookUrl", e.target.value)}
                                placeholder="https://api.example.com/hook"
                                disabled={readOnly || func.isBuiltin}
                                className="text-sm h-8"
                            />
                        </div>
                    </div>

                    <div>
                        <Label className="text-xs">Description (shown to LLM)</Label>
                        <Textarea
                            value={func.description}
                            onChange={(e) => handleFieldChange("description", e.target.value)}
                            placeholder="Describe what this function does..."
                            rows={2}
                            disabled={readOnly || func.isBuiltin}
                            className="text-sm resize-none"
                        />
                    </div>

                    {/* Parameters */}
                    <div>
                        <div className="flex items-center justify-between mb-1.5">
                            <Label className="text-xs">Parameters</Label>
                            {!readOnly && !func.isBuiltin && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleAddParam}
                                    className="h-6 text-xs gap-1 px-2"
                                >
                                    <Plus className="h-3 w-3" />
                                    Add
                                </Button>
                            )}
                        </div>

                        {func.parameters.length > 0 ? (
                            <div className="space-y-1.5">
                                {func.parameters.map((param, paramIndex) => (
                                    <div
                                        key={paramIndex}
                                        className="flex items-center gap-2 rounded-md bg-muted/50 px-2 py-1.5"
                                    >
                                        <Input
                                            value={param.name}
                                            onChange={(e) =>
                                                handleUpdateParam(paramIndex, { ...param, name: e.target.value })
                                            }
                                            placeholder="param_name"
                                            disabled={readOnly || func.isBuiltin}
                                            className="w-28 h-7 text-xs font-mono"
                                        />
                                        <Select
                                            value={param.type}
                                            onValueChange={(val) =>
                                                handleUpdateParam(paramIndex, {
                                                    ...param,
                                                    type: val as FunctionParameter["type"],
                                                })
                                            }
                                            disabled={readOnly || func.isBuiltin}
                                        >
                                            <SelectTrigger className="w-24 h-7 text-xs">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="string">string</SelectItem>
                                                <SelectItem value="number">number</SelectItem>
                                                <SelectItem value="boolean">boolean</SelectItem>
                                                <SelectItem value="object">object</SelectItem>
                                                <SelectItem value="array">array</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <Input
                                            value={param.description}
                                            onChange={(e) =>
                                                handleUpdateParam(paramIndex, {
                                                    ...param,
                                                    description: e.target.value,
                                                })
                                            }
                                            placeholder="Description"
                                            disabled={readOnly || func.isBuiltin}
                                            className="flex-1 h-7 text-xs"
                                        />
                                        <div className="flex items-center gap-1">
                                            <Label className="text-[10px] text-muted-foreground">Req</Label>
                                            <Switch
                                                checked={param.required}
                                                onCheckedChange={(val) =>
                                                    handleUpdateParam(paramIndex, { ...param, required: val })
                                                }
                                                disabled={readOnly || func.isBuiltin}
                                                className="scale-75"
                                            />
                                        </div>
                                        {!readOnly && !func.isBuiltin && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => handleRemoveParam(paramIndex)}
                                                className="h-6 w-6 text-destructive hover:text-destructive"
                                            >
                                                <Trash2 className="h-3 w-3" />
                                            </Button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground py-1">
                                No parameters — function takes no arguments.
                            </p>
                        )}
                    </div>

                    {/* Delete button (custom functions only) */}
                    {!readOnly && !func.isBuiltin && (
                        <div className="flex justify-end pt-1">
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => onRemove(index)}
                                className="gap-1 text-xs"
                            >
                                <Trash2 className="h-3 w-3" />
                                Remove Function
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
