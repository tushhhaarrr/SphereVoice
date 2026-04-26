"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useScenarioResults } from "../../hooks/use-test-scenarios";
import { TestResults } from "./test-results";
import type { TestCallResult } from "../../types";

interface ScenarioHistoryProps {
    agentId: string;
    scenarioId: string;
}

function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

export function ScenarioHistory({ agentId, scenarioId }: ScenarioHistoryProps) {
    const { data, isLoading } = useScenarioResults(agentId, scenarioId);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    if (isLoading) {
        return <p className="text-xs text-muted-foreground py-2">Loading results...</p>;
    }

    const results = data?.results ?? [];

    if (results.length === 0) {
        return (
            <p className="text-xs text-muted-foreground py-2">
                No test runs yet. Click the play button to run this scenario.
            </p>
        );
    }

    return (
        <div className="space-y-1.5 pt-1 border-t">
            <span className="text-xs font-medium text-muted-foreground">
                History ({results.length} run{results.length !== 1 ? "s" : ""})
            </span>
            {results.map((result) => (
                <ScenarioRunRow
                    key={result.id}
                    result={result}
                    expanded={expandedId === result.id}
                    onToggle={() =>
                        setExpandedId(expandedId === result.id ? null : result.id)
                    }
                />
            ))}
        </div>
    );
}

function ScenarioRunRow({
    result,
    expanded,
    onToggle,
}: {
    result: TestCallResult;
    expanded: boolean;
    onToggle: () => void;
}) {
    return (
        <div className="rounded-md border bg-background">
            <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-muted/50 transition-colors"
                onClick={onToggle}
            >
                <div className="flex items-center gap-2">
                    {result.passed ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                    ) : (
                        <XCircle className="h-3.5 w-3.5 text-destructive flex-shrink-0" />
                    )}
                    <span className="text-xs">
                        {result.matched_fields}/{result.total_fields} fields
                    </span>
                    {result.agent_version != null && (
                        <Badge variant="outline" className="text-[10px] px-1 py-0">
                            v{result.agent_version}
                        </Badge>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">
                        {formatDate(result.created_at)}
                    </span>
                    {result.call_id && (
                        <a
                            href={`/calls?callId=${result.call_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-muted-foreground hover:text-foreground"
                            title="View call"
                        >
                            <ExternalLink className="h-3 w-3" />
                        </a>
                    )}
                    {expanded ? (
                        <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                </div>
            </button>

            {expanded && (
                <div className="px-3 pb-3 pt-1 border-t">
                    <TestResults result={result} />
                </div>
            )}
        </div>
    );
}
