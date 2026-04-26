"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Variable, FileOutput } from "lucide-react";
import { useAgents } from "@/modules/agents";
import { useAgentPromptVariables } from "../../hooks/use-campaigns";
import type { CampaignWizardData } from "../../types";

export interface StepAgentSelectProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
    tenantId: string;
}

export function StepAgentSelect({
    data,
    onUpdate,
    tenantId,
}: StepAgentSelectProps) {
    const { data: agentsData, isLoading } = useAgents({ tenantId });
    const { data: promptData } = useAgentPromptVariables(data.agent_id);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const agents = agentsData?.agents ?? [];

    return (
        <div className="space-y-4">
            <div>
                <h2 className="text-lg font-semibold">Select Agent</h2>
                <p className="text-sm text-muted-foreground">
                    Choose an AI agent to handle calls for this campaign.
                    The agent&apos;s prompt variables and extraction fields will
                    be used for CRM field mapping.
                </p>
            </div>

            {agents.length === 0 ? (
                <div className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
                    No agents found. Create an agent first.
                </div>
            ) : (
                <div className="grid gap-3">
                    {agents.map((agent) => (
                        <Card
                            key={agent.id}
                            className={`cursor-pointer transition-colors hover:bg-muted/50 ${data.agent_id === agent.id
                                ? "border-primary ring-1 ring-primary"
                                : ""
                                }`}
                            onClick={() => onUpdate({ agent_id: agent.id })}
                        >
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">
                                    {agent.name}
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pb-3">
                                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                    <span className="capitalize">{agent.type}</span>
                                    <span className="capitalize">{agent.status}</span>
                                    <span className="capitalize">{agent.call_direction}</span>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Agent prompt analysis — shown when an agent is selected */}
            {data.agent_id && promptData && (
                <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
                    <h3 className="text-sm font-semibold">
                        Agent: {promptData.agent_name}
                    </h3>

                    {/* Prompt variables */}
                    <div className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                            <Variable className="h-3.5 w-3.5" />
                            Template Variables ({promptData.prompt_variables.length})
                        </div>
                        {promptData.prompt_variables.length > 0 ? (
                            <div className="space-y-1">
                                {promptData.prompt_variables.map((v) => {
                                    const sources = promptData.vars_by_source
                                        ? Object.entries(promptData.vars_by_source)
                                            .filter(([, vars]) => vars.includes(v))
                                            .map(([src]) =>
                                                src.startsWith("node:") ? src.slice(5) :
                                                    src === "system_prompt" ? "Prompt" :
                                                        src === "global_prompt" ? "Global" :
                                                            src === "welcome_message" ? "Welcome" :
                                                                src === "defined" ? "Defined" : src
                                            )
                                        : [];
                                    const defined = promptData.defined_variables?.find(
                                        (d) => d.name === v
                                    );
                                    return (
                                        <div key={v} className="flex items-center gap-2">
                                            <Badge variant="secondary" className="text-xs font-mono">
                                                {`{{${v}}}`}
                                            </Badge>
                                            {sources.length > 0 && (
                                                <span className="text-[10px] text-muted-foreground">
                                                    {sources.join(", ")}
                                                </span>
                                            )}
                                            {defined?.default_value && (
                                                <span className="text-[10px] text-muted-foreground italic">
                                                    default: &quot;{defined.default_value}&quot;
                                                </span>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground">
                                No template variables found. Add{" "}
                                <code className="text-[10px]">{`{{variable_name}}`}</code> to
                                the prompt, welcome message, or flow nodes to use dynamic CRM data.
                            </p>
                        )}
                    </div>

                    {/* Extraction fields */}
                    <div className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                            <FileOutput className="h-3.5 w-3.5" />
                            Extraction Fields (Write-Back)
                        </div>
                        {promptData.extraction_fields.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                                {promptData.extraction_fields.map((f, i) => (
                                    <Badge key={i} variant="outline" className="text-xs font-mono">
                                        {(f as { name?: string }).name || `field_${i}`}
                                    </Badge>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground">
                                No extraction fields defined. Configure extraction fields in the
                                agent settings to enable CRM write-back.
                            </p>
                        )}
                    </div>

                    {/* Prompt preview */}
                    {promptData.prompt_preview && (
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">
                                Prompt Preview
                            </p>
                            <pre className="rounded bg-background p-2 text-[11px] leading-relaxed text-muted-foreground max-h-32 overflow-y-auto whitespace-pre-wrap">
                                {promptData.prompt_preview}
                            </pre>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
