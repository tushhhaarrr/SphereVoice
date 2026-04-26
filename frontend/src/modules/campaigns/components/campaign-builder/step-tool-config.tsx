"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CampaignWizardData } from "../../types";

export interface StepToolConfigProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
}

export function StepToolConfig({ data, onUpdate }: StepToolConfigProps) {
    const [newKey, setNewKey] = useState("");
    const [newValue, setNewValue] = useState("");

    const entries = Object.entries(data.tool_config);

    function addEntry() {
        if (!newKey.trim()) return;
        let parsed: unknown = newValue;
        try {
            parsed = JSON.parse(newValue);
        } catch {
            // keep as string
        }
        onUpdate({
            tool_config: {
                ...data.tool_config,
                [newKey.trim()]: parsed,
            },
        });
        setNewKey("");
        setNewValue("");
    }

    function removeEntry(key: string) {
        const updated = { ...data.tool_config };
        delete updated[key];
        onUpdate({ tool_config: updated });
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">Tool Configuration</h2>
                <p className="text-sm text-muted-foreground">
                    Optional overrides for tool execution during calls. These
                    key-value pairs are passed to function-calling tools at
                    runtime.
                </p>
            </div>

            {/* Existing entries */}
            {entries.length > 0 && (
                <div className="space-y-2">
                    {entries.map(([key, value]) => (
                        <div
                            key={key}
                            className="flex items-center gap-2 rounded-md border px-3 py-2"
                        >
                            <span className="text-sm font-medium">{key}</span>
                            <span className="text-sm text-muted-foreground">
                                =
                            </span>
                            <span className="flex-1 truncate text-sm font-mono">
                                {typeof value === "string"
                                    ? value
                                    : JSON.stringify(value)}
                            </span>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => removeEntry(key)}
                                className="h-7 w-7 text-destructive"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    ))}
                </div>
            )}

            {/* Add new */}
            <div className="space-y-3 rounded-lg border p-4">
                <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                        <Label htmlFor="tool-key">Key</Label>
                        <Input
                            id="tool-key"
                            placeholder="webhook_url"
                            value={newKey}
                            onChange={(e) => setNewKey(e.target.value)}
                        />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="tool-value">Value</Label>
                        <Input
                            id="tool-value"
                            placeholder="https://..."
                            value={newValue}
                            onChange={(e) => setNewValue(e.target.value)}
                        />
                    </div>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={addEntry}
                    disabled={!newKey.trim()}
                >
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Config
                </Button>
            </div>

            {entries.length === 0 && (
                <p className="text-sm text-muted-foreground">
                    No tool config defined. This step is optional — skip if your
                    agent&apos;s tools don&apos;t require runtime overrides.
                </p>
            )}
        </div>
    );
}
