"use client";

import { useState } from "react";
import { Plus, FlaskConical, Trash2, Edit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    useTestScenarios,
    useDeleteScenario,
} from "../../hooks/use-test-scenarios";
import { ScenarioForm } from "./scenario-form";
import { RunScenario } from "./run-scenario";
import { ScenarioHistory } from "./scenario-history";
import type { TestScenario } from "../../types";

interface ScenarioListProps {
    agentId: string;
}

export function ScenarioList({ agentId }: ScenarioListProps) {
    const scenarios = useTestScenarios(agentId);
    const deleteMutation = useDeleteScenario(agentId);
    const [showForm, setShowForm] = useState(false);
    const [editingScenario, setEditingScenario] = useState<TestScenario | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const handleEdit = (scenario: TestScenario) => {
        setEditingScenario(scenario);
        setShowForm(true);
    };

    const handleFormClose = () => {
        setShowForm(false);
        setEditingScenario(null);
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-medium">Test Scenarios</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                        Create test cases with pre-filled context and expected extraction outcomes
                    </p>
                </div>
                <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    New Scenario
                </Button>
            </div>

            {showForm && (
                <ScenarioForm
                    agentId={agentId}
                    scenario={editingScenario}
                    onClose={handleFormClose}
                />
            )}

            {scenarios.isLoading && (
                <p className="text-sm text-muted-foreground">Loading scenarios...</p>
            )}

            {scenarios.data?.scenarios.length === 0 && !scenarios.isLoading && (
                <Card>
                    <CardContent className="py-8 text-center text-sm text-muted-foreground">
                        <FlaskConical className="mx-auto mb-2 h-8 w-8 opacity-50" />
                        No test scenarios yet. Create one to start validating agent behaviour.
                    </CardContent>
                </Card>
            )}

            {scenarios.data?.scenarios.map((scenario) => (
                <Card key={scenario.id}>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-medium">{scenario.name}</CardTitle>
                            <div className="flex items-center gap-1">
                                <RunScenario agentId={agentId} scenarioId={scenario.id} />
                                <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-7 w-7"
                                    onClick={() => handleEdit(scenario)}
                                >
                                    <Edit className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-7 w-7 text-destructive"
                                    onClick={() => deleteMutation.mutate(scenario.id)}
                                    disabled={deleteMutation.isPending}
                                >
                                    <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {scenario.description && (
                            <p className="text-xs text-muted-foreground">{scenario.description}</p>
                        )}

                        <div className="flex flex-wrap gap-1">
                            {Object.entries(scenario.dynamic_variables).map(([key, value]) => (
                                <Badge key={key} variant="secondary" className="text-xs font-mono">
                                    {key}: {String(value).slice(0, 30)}
                                </Badge>
                            ))}
                        </div>

                        {Object.keys(scenario.expected_outcomes).length > 0 && (
                            <div className="flex flex-wrap gap-1">
                                <span className="text-xs text-muted-foreground mr-1">Expected:</span>
                                {Object.entries(scenario.expected_outcomes).map(([key, value]) => (
                                    <Badge key={key} variant="outline" className="text-xs font-mono">
                                        {key}={String(value).slice(0, 20)}
                                    </Badge>
                                ))}
                            </div>
                        )}

                        <Button
                            variant="link"
                            size="sm"
                            className="h-auto p-0 text-xs"
                            onClick={() => setExpandedId(expandedId === scenario.id ? null : scenario.id)}
                        >
                            {expandedId === scenario.id ? "Hide history" : "Show history"}
                        </Button>

                        {expandedId === scenario.id && (
                            <ScenarioHistory agentId={agentId} scenarioId={scenario.id} />
                        )}
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
