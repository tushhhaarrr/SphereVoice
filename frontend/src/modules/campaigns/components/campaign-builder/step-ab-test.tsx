"use client";

import { useState } from "react";
import { FlaskConical, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useAgents } from "@/modules/agents";
import type { CampaignWizardData } from "../../types";

export interface StepAbTestProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
    tenantId: string;
}

export function StepAbTest({ data, onUpdate, tenantId }: StepAbTestProps) {
    const { data: agentsData, isLoading } = useAgents({ tenantId });
    const [enabled, setEnabled] = useState(!!data.variant_agent_id);

    const agents = agentsData?.agents ?? [];
    // Exclude the primary agent from variant selection
    const availableVariants = agents.filter((a) => a.id !== data.agent_id);

    function handleToggle(checked: boolean) {
        setEnabled(checked);
        if (!checked) {
            onUpdate({ variant_agent_id: "", ab_split_percent: 50 });
        }
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">A/B Testing (Optional)</h2>
                <p className="text-sm text-muted-foreground">
                    Split your contact list between two agents to compare performance.
                    Skip this step if you don&apos;t want to run an A/B test.
                </p>
            </div>

            {/* Enable toggle */}
            <div className="flex items-center gap-3">
                <Switch id="ab-toggle" checked={enabled} onCheckedChange={handleToggle} />
                <Label htmlFor="ab-toggle" className="cursor-pointer">
                    Enable A/B Testing
                </Label>
            </div>

            {enabled && (
                <>
                    {/* Variant Agent Selection */}
                    <div className="space-y-2">
                        <Label>Variant Agent (Agent B)</Label>
                        {isLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Loading agents…
                            </div>
                        ) : availableVariants.length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                                No other agents available. Create another agent to use A/B testing.
                            </p>
                        ) : (
                            <div className="grid gap-2">
                                {availableVariants.map((agent) => {
                                    const isSelected = data.variant_agent_id === agent.id;
                                    return (
                                        <Card
                                            key={agent.id}
                                            className={`cursor-pointer transition-colors hover:border-primary ${isSelected ? "border-primary bg-primary/5" : ""
                                                }`}
                                            onClick={() => onUpdate({ variant_agent_id: agent.id })}
                                        >
                                            <CardContent className="flex items-center justify-between py-3">
                                                <div>
                                                    <p className="font-medium">{agent.name}</p>
                                                    {agent.description && (
                                                        <p className="text-xs text-muted-foreground line-clamp-1">
                                                            {agent.description}
                                                        </p>
                                                    )}
                                                </div>
                                                {isSelected && (
                                                    <Badge className="bg-primary">Selected</Badge>
                                                )}
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Split Percentage */}
                    <div className="space-y-3">
                        <Label>
                            Traffic Split: Agent A gets{" "}
                            <span className="font-mono font-bold">{data.ab_split_percent}%</span>
                            , Agent B gets{" "}
                            <span className="font-mono font-bold">{100 - data.ab_split_percent}%</span>
                        </Label>
                        <Slider
                            value={[data.ab_split_percent]}
                            onValueChange={([v]) => onUpdate({ ab_split_percent: v })}
                            min={10}
                            max={90}
                            step={5}
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                            <span>Mostly Agent A</span>
                            <span>50/50</span>
                            <span>Mostly Agent B</span>
                        </div>
                    </div>

                    {/* Info card */}
                    <Card className="bg-muted/50">
                        <CardContent className="flex items-start gap-3 pt-4">
                            <FlaskConical className="mt-0.5 h-5 w-5 text-muted-foreground" />
                            <div className="text-sm text-muted-foreground">
                                <p className="font-medium text-foreground">How A/B testing works</p>
                                <p className="mt-1">
                                    Each contact is randomly assigned to Agent A or Agent B based
                                    on the split percentage. After the campaign completes, go to
                                    the Analytics tab to see side-by-side performance comparison.
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}
