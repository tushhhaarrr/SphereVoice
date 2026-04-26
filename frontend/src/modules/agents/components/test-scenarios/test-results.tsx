"use client";

import { CheckCircle2, XCircle, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import type { TestCallResult, MatchField } from "../../types";

interface TestResultsProps {
    result: TestCallResult;
}

export function TestResults({ result }: TestResultsProps) {
    const fields: MatchField[] = result.match_results?.fields ?? [];

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                {result.passed ? (
                    <Badge variant="default" className="bg-green-600">
                        <CheckCircle2 className="mr-1 h-3 w-3" />
                        Passed
                    </Badge>
                ) : (
                    <Badge variant="destructive">
                        <XCircle className="mr-1 h-3 w-3" />
                        Failed
                    </Badge>
                )}
                <span className="text-xs text-muted-foreground">
                    {result.matched_fields}/{result.total_fields} fields matched
                </span>
                {result.agent_version != null && (
                    <Badge variant="outline" className="text-xs">
                        v{result.agent_version}
                    </Badge>
                )}
            </div>

            {fields.length > 0 && (
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-8"></TableHead>
                            <TableHead className="text-xs">Field</TableHead>
                            <TableHead className="text-xs">Expected</TableHead>
                            <TableHead className="text-xs">Actual</TableHead>
                            <TableHead className="text-xs w-16">Strategy</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {fields.map((field) => (
                            <TableRow key={field.field}>
                                <TableCell className="py-1.5">
                                    {field.match ? (
                                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                                    ) : (
                                        <XCircle className="h-4 w-4 text-destructive" />
                                    )}
                                </TableCell>
                                <TableCell className="py-1.5 font-mono text-xs">
                                    {field.field}
                                </TableCell>
                                <TableCell className="py-1.5 text-xs max-w-[120px] truncate">
                                    {String(field.expected ?? "—")}
                                </TableCell>
                                <TableCell className="py-1.5 text-xs max-w-[120px] truncate">
                                    {field.actual != null ? String(field.actual) : (
                                        <span className="text-muted-foreground italic">missing</span>
                                    )}
                                </TableCell>
                                <TableCell className="py-1.5">
                                    <Badge variant="outline" className="text-[10px] px-1 py-0">
                                        {field.strategy}
                                    </Badge>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            )}
        </div>
    );
}
