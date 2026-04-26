"use client";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAgents } from "@/modules/agents";
import type { CampaignWizardData } from "../../types";

export interface StepReviewProps {
    data: CampaignWizardData;
    tenantId: string;
}

export function StepReview({ data, tenantId }: StepReviewProps) {
    const { data: agentsData } = useAgents({ tenantId });
    const agent = agentsData?.agents?.find((a) => a.id === data.agent_id);

    const variableEntries = Object.entries(data.variable_mapping);
    const writebackEntries = Object.entries(data.writeback_mapping);
    const toolEntries = Object.entries(data.tool_config);

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">Review &amp; Launch</h2>
                <p className="text-sm text-muted-foreground">
                    Review your campaign configuration before creating it.
                </p>
            </div>

            {/* Agent */}
            <Section title="Agent">
                <Row label="Agent" value={agent?.name ?? data.agent_id} />
            </Section>

            <Separator />

            {/* Source */}
            <Section title="CRM Source">
                <Row label="Source Type" value={data.source_type || "manual"} />
                {Object.entries(data.source_config).map(([k, v]) => (
                    <Row key={k} label={k} value={String(v)} />
                ))}
            </Section>

            <Separator />

            {/* Variable Mapping */}
            <Section title="Variable Mapping">
                {variableEntries.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None</p>
                ) : (
                    variableEntries.map(([k, v]) => (
                        <Row key={k} label={k} value={v} />
                    ))
                )}
            </Section>

            <Separator />

            {/* Write-Back Mapping */}
            <Section title="Write-Back Mapping">
                {writebackEntries.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None</p>
                ) : (
                    writebackEntries.map(([k, v]) => (
                        <Row key={k} label={k} value={v} />
                    ))
                )}
            </Section>

            <Separator />

            {/* Call Settings */}
            <Section title="Call Settings">
                <Row label="Name" value={data.name || "—"} />
                <Row label="Description" value={data.description || "—"} />
                <Row label="From Number" value={data.from_number || "Default"} />
                <Row
                    label="Max Concurrent"
                    value={String(data.max_concurrent)}
                />
                <Row
                    label="Calls/Minute"
                    value={String(data.calls_per_minute)}
                />
                <Row label="Max Retries" value={String(data.max_retries)} />
                <Row
                    label="Retry Delay"
                    value={`${data.retry_delay_minutes} min`}
                />
            </Section>

            <Separator />

            {/* Tool Config */}
            <Section title="Tool Config">
                {toolEntries.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None</p>
                ) : (
                    toolEntries.map(([k, v]) => (
                        <Row
                            key={k}
                            label={k}
                            value={
                                typeof v === "string" ? v : JSON.stringify(v)
                            }
                        />
                    ))
                )}
            </Section>

            {/* Validation hint */}
            {!data.agent_id && (
                <Badge variant="destructive">
                    Agent is required — go back to Step 1.
                </Badge>
            )}
            {!data.name && (
                <Badge variant="destructive">
                    Campaign name is required — go back to Step 5.
                </Badge>
            )}
        </div>
    );
}

// ── Helper sub-components ────────────────────────────────────

function Section({
    title,
    children,
}: {
    title: string;
    children: React.ReactNode;
}) {
    return (
        <div className="space-y-2">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                {title}
            </h3>
            <div className="space-y-1">{children}</div>
        </div>
    );
}

function Row({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-medium">{value}</span>
        </div>
    );
}
