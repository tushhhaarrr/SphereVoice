"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plus, X, Save } from "lucide-react";
import {
    useCreateScenario,
    useUpdateScenario,
} from "../../hooks/use-test-scenarios";
import type { TestScenario } from "../../types";

interface ScenarioFormProps {
    agentId: string;
    scenario: TestScenario | null;
    onClose: () => void;
}

interface KeyValuePair {
    key: string;
    value: string;
}

function toKeyValuePairs(obj: Record<string, unknown>): KeyValuePair[] {
    const entries = Object.entries(obj);
    return entries.length > 0
        ? entries.map(([key, value]) => ({ key, value: String(value) }))
        : [{ key: "", value: "" }];
}

function fromKeyValuePairs(pairs: KeyValuePair[]): Record<string, string> {
    const result: Record<string, string> = {};
    for (const { key, value } of pairs) {
        if (key.trim()) {
            result[key.trim()] = value;
        }
    }
    return result;
}

export function ScenarioForm({ agentId, scenario, onClose }: ScenarioFormProps) {
    const isEditing = !!scenario;
    const createMutation = useCreateScenario(agentId);
    const updateMutation = useUpdateScenario(agentId, scenario?.id ?? "");

    const [name, setName] = useState(scenario?.name ?? "");
    const [description, setDescription] = useState(scenario?.description ?? "");
    const [variables, setVariables] = useState<KeyValuePair[]>(
        toKeyValuePairs((scenario?.dynamic_variables ?? {}) as Record<string, unknown>),
    );
    const [outcomes, setOutcomes] = useState<KeyValuePair[]>(
        toKeyValuePairs((scenario?.expected_outcomes ?? {}) as Record<string, unknown>),
    );

    const updatePair = (
        list: KeyValuePair[],
        index: number,
        field: "key" | "value",
        value: string,
        setter: (v: KeyValuePair[]) => void,
    ) => {
        const next = [...list];
        next[index] = { ...next[index], [field]: value };
        setter(next);
    };

    const addPair = (list: KeyValuePair[], setter: (v: KeyValuePair[]) => void) => {
        setter([...list, { key: "", value: "" }]);
    };

    const removePair = (list: KeyValuePair[], index: number, setter: (v: KeyValuePair[]) => void) => {
        const next = list.filter((_, i) => i !== index);
        setter(next.length > 0 ? next : [{ key: "", value: "" }]);
    };

    const handleSubmit = () => {
        if (!name.trim()) return;

        const data = {
            name: name.trim(),
            description: description.trim() || undefined,
            dynamic_variables: fromKeyValuePairs(variables),
            expected_outcomes: fromKeyValuePairs(outcomes),
        };

        if (isEditing) {
            updateMutation.mutate(data, { onSuccess: onClose });
        } else {
            createMutation.mutate(data, { onSuccess: onClose });
        }
    };

    const isPending = createMutation.isPending || updateMutation.isPending;

    return (
        <Card className="border-primary/30">
            <CardHeader className="pb-3">
                <CardTitle className="text-sm">
                    {isEditing ? "Edit Scenario" : "New Test Scenario"}
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="scenario-name" className="text-xs">Name</Label>
                    <Input
                        id="scenario-name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Hot lead follow-up call"
                        className="h-8 text-sm"
                    />
                </div>

                <div className="space-y-2">
                    <Label htmlFor="scenario-desc" className="text-xs">Description (optional)</Label>
                    <Textarea
                        id="scenario-desc"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Simulates a warm MBA lead from Mumbai..."
                        rows={2}
                        className="text-sm"
                    />
                </div>

                {/* Dynamic Variables */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs">Dynamic Variables (CRM context)</Label>
                        <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-xs"
                            onClick={() => addPair(variables, setVariables)}
                        >
                            <Plus className="mr-1 h-3 w-3" />
                            Add
                        </Button>
                    </div>
                    {variables.map((pair, i) => (
                        <div key={i} className="flex items-center gap-2">
                            <Input
                                value={pair.key}
                                onChange={(e) => updatePair(variables, i, "key", e.target.value, setVariables)}
                                placeholder="caller_name"
                                className="h-7 flex-1 text-xs font-mono"
                            />
                            <Input
                                value={pair.value}
                                onChange={(e) => updatePair(variables, i, "value", e.target.value, setVariables)}
                                placeholder="Rahul Sharma"
                                className="h-7 flex-1 text-xs"
                            />
                            <Button
                                size="icon"
                                variant="ghost"
                                className="h-6 w-6"
                                onClick={() => removePair(variables, i, setVariables)}
                            >
                                <X className="h-3 w-3" />
                            </Button>
                        </div>
                    ))}
                </div>

                {/* Expected Outcomes */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs">Expected Extraction Outcomes</Label>
                        <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-xs"
                            onClick={() => addPair(outcomes, setOutcomes)}
                        >
                            <Plus className="mr-1 h-3 w-3" />
                            Add
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Use exact values, *contains*, ^regex$, or any_date / any_string wildcards
                    </p>
                    {outcomes.map((pair, i) => (
                        <div key={i} className="flex items-center gap-2">
                            <Input
                                value={pair.key}
                                onChange={(e) => updatePair(outcomes, i, "key", e.target.value, setOutcomes)}
                                placeholder="qualification_status"
                                className="h-7 flex-1 text-xs font-mono"
                            />
                            <Input
                                value={pair.value}
                                onChange={(e) => updatePair(outcomes, i, "value", e.target.value, setOutcomes)}
                                placeholder="Hot Lead"
                                className="h-7 flex-1 text-xs"
                            />
                            <Button
                                size="icon"
                                variant="ghost"
                                className="h-6 w-6"
                                onClick={() => removePair(outcomes, i, setOutcomes)}
                            >
                                <X className="h-3 w-3" />
                            </Button>
                        </div>
                    ))}
                </div>

                <div className="flex items-center justify-end gap-2">
                    <Button size="sm" variant="ghost" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button size="sm" onClick={handleSubmit} disabled={isPending || !name.trim()}>
                        <Save className="mr-1.5 h-3.5 w-3.5" />
                        {isPending ? "Saving..." : isEditing ? "Update" : "Create"}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
