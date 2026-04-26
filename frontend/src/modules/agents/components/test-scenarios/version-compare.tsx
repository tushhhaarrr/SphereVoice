"use client";

import { CheckCircle2, XCircle, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TestCallResult, MatchField } from "../../types";

interface VersionCompareProps {
    left: TestCallResult;
    right: TestCallResult;
}

export function VersionCompare({ left, right }: VersionCompareProps) {
    const leftFields = left.match_results?.fields ?? [];
    const rightFields = right.match_results?.fields ?? [];

    // Collect all unique field names
    const allFieldNames = Array.from(
        new Set([
            ...leftFields.map((f) => f.field),
            ...rightFields.map((f) => f.field),
        ]),
    );

    const leftMap = new Map(leftFields.map((f) => [f.field, f]));
    const rightMap = new Map(rightFields.map((f) => [f.field, f]));

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="grid grid-cols-2 gap-4">
                <ResultHeader result={left} label="Left" />
                <ResultHeader result={right} label="Right" />
            </div>

            {/* Field-by-field comparison */}
            <div className="border rounded-lg overflow-hidden">
                {/* Table header */}
                <div className="grid grid-cols-[1fr_1fr_1fr] text-[10px] font-medium text-muted-foreground uppercase bg-muted/50 px-3 py-1.5">
                    <span>Field</span>
                    <span className="text-center">
                        v{left.agent_version ?? "?"}
                    </span>
                    <span className="text-center">
                        v{right.agent_version ?? "?"}
                    </span>
                </div>

                {allFieldNames.map((fieldName) => {
                    const lf = leftMap.get(fieldName);
                    const rf = rightMap.get(fieldName);
                    const changed = fieldsDiffer(lf, rf);

                    return (
                        <div
                            key={fieldName}
                            className={`grid grid-cols-[1fr_1fr_1fr] items-center text-xs px-3 py-2 border-t ${changed ? "bg-yellow-50 dark:bg-yellow-950/30" : ""
                                }`}
                        >
                            {/* Field name */}
                            <span className="font-mono truncate">{fieldName}</span>

                            {/* Left result */}
                            <FieldCell field={lf} />

                            {/* Right result */}
                            <FieldCell field={rf} />
                        </div>
                    );
                })}
            </div>

            {/* Score comparison */}
            <div className="flex items-center justify-center gap-3 text-sm">
                <ScorePill result={left} />
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                <ScorePill result={right} />
            </div>
        </div>
    );
}

function ResultHeader({
    result,
    label,
}: {
    result: TestCallResult;
    label: string;
}) {
    return (
        <Card>
            <CardHeader className="pb-1 pt-3 px-3">
                <CardTitle className="text-xs flex items-center gap-2">
                    {result.passed ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                    ) : (
                        <XCircle className="h-3.5 w-3.5 text-destructive" />
                    )}
                    {result.agent_version != null ? `Version ${result.agent_version}` : label}
                </CardTitle>
            </CardHeader>
            <CardContent className="pb-3 px-3">
                <span className="text-xs text-muted-foreground">
                    {result.matched_fields}/{result.total_fields} fields matched
                </span>
            </CardContent>
        </Card>
    );
}

function FieldCell({ field }: { field: MatchField | undefined }) {
    if (!field) {
        return (
            <span className="text-center text-muted-foreground italic">—</span>
        );
    }

    return (
        <div className="flex items-center justify-center gap-1.5">
            {field.match ? (
                <CheckCircle2 className="h-3 w-3 text-green-600 flex-shrink-0" />
            ) : (
                <XCircle className="h-3 w-3 text-destructive flex-shrink-0" />
            )}
            <span className="truncate max-w-[80px]">
                {field.actual != null ? String(field.actual) : "—"}
            </span>
        </div>
    );
}

function ScorePill({ result }: { result: TestCallResult }) {
    return (
        <Badge variant={result.passed ? "default" : "destructive"} className="text-xs">
            {result.matched_fields}/{result.total_fields}
            {result.agent_version != null && ` (v${result.agent_version})`}
        </Badge>
    );
}

function fieldsDiffer(
    a: MatchField | undefined,
    b: MatchField | undefined,
): boolean {
    if (!a || !b) return true;
    return a.match !== b.match || String(a.actual) !== String(b.actual);
}
