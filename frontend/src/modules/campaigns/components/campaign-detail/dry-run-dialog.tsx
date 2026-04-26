"use client";

import { useState } from "react";
import {
    ArrowRight,
    ChevronDown,
    ChevronRight,
    FlaskConical,
    Loader2,
    MessageSquare,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useDryRun } from "../../hooks/use-campaigns";
import type { DryRunContactResult } from "../../hooks/use-campaigns";

interface DryRunDialogProps {
    campaignId: string;
    tenantId?: string;
    disabled?: boolean;
    hasContacts: boolean;
}

export function DryRunDialog({
    campaignId,
    tenantId,
    disabled,
    hasContacts,
}: DryRunDialogProps) {
    const [open, setOpen] = useState(false);
    const dryRun = useDryRun(campaignId, tenantId);

    const handleRun = () => {
        dryRun.mutate(1);
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button
                    variant="outline"
                    size="sm"
                    disabled={disabled || !hasContacts}
                    onClick={() => {
                        setOpen(true);
                        if (!dryRun.data) {
                            dryRun.mutate(1);
                        }
                    }}
                >
                    <FlaskConical className="mr-1 h-4 w-4" />
                    Test Run
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl max-h-[85vh]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <FlaskConical className="h-5 w-5" />
                        Campaign Test Run
                    </DialogTitle>
                    <DialogDescription>
                        Simulates a call with real CRM data — no actual phone call is made.
                        Tests variable injection, conversation flow, extraction, and CRM
                        write-back mapping end-to-end.
                    </DialogDescription>
                </DialogHeader>

                {dryRun.isPending && (
                    <div className="flex flex-col items-center justify-center gap-3 py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">
                            Simulating conversation with LLM…
                        </p>
                        <p className="text-xs text-muted-foreground">
                            This takes 10-20 seconds
                        </p>
                    </div>
                )}

                {dryRun.isError && (
                    <div className="space-y-3 py-4">
                        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                            {dryRun.error.message}
                        </div>
                        <Button variant="outline" size="sm" onClick={handleRun}>
                            Retry
                        </Button>
                    </div>
                )}

                {dryRun.data && (
                    <ScrollArea className="max-h-[65vh] pr-2">
                        <div className="space-y-4">
                            {/* Warnings */}
                            {dryRun.data.warnings.length > 0 && (
                                <div className="space-y-1">
                                    {dryRun.data.warnings.map((w, i) => (
                                        <div
                                            key={i}
                                            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300"
                                        >
                                            {w}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {dryRun.data.results.length === 0 && (
                                <p className="text-sm text-muted-foreground py-8 text-center">
                                    No contacts to test. Load contacts first.
                                </p>
                            )}

                            {/* Results */}
                            {dryRun.data.results.map((result, i) => (
                                <ContactDryRunResult
                                    key={i}
                                    result={result}
                                    agentName={dryRun.data.agent_name}
                                />
                            ))}

                            {/* Re-run button */}
                            <div className="flex justify-center pt-2 pb-1">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleRun}
                                    disabled={dryRun.isPending}
                                >
                                    {dryRun.isPending ? (
                                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
                                    )}
                                    Run Again
                                </Button>
                            </div>
                        </div>
                    </ScrollArea>
                )}
            </DialogContent>
        </Dialog>
    );
}

// ─── Single Contact Result ───────────────────────────────────────────────────

function ContactDryRunResult({
    result,
    agentName,
}: {
    result: DryRunContactResult;
    agentName: string;
}) {
    const [expandedSections, setExpandedSections] = useState<Set<string>>(
        new Set(["transcript", "extraction", "writeback"])
    );

    const toggle = (section: string) => {
        setExpandedSections((prev) => {
            const next = new Set(prev);
            if (next.has(section)) {
                next.delete(section);
            } else {
                next.add(section);
            }
            return next;
        });
    };

    const variableEntries = Object.entries(result.resolved_variables);
    const extractionEntries = Object.entries(result.extracted_data);
    const writebackEntries = Object.entries(result.writeback_preview);

    return (
        <div className="rounded-lg border p-4 space-y-3">
            {/* Contact header */}
            <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-medium">
                    {result.phone_number}
                </span>
                <Badge variant="outline" className="text-xs">
                    Simulated
                </Badge>
            </div>

            {/* Variable injection */}
            {variableEntries.length > 0 && (
                <CollapsibleSection
                    title="Injected Variables"
                    count={variableEntries.length}
                    expanded={expandedSections.has("variables")}
                    onToggle={() => toggle("variables")}
                >
                    <div className="grid gap-1">
                        {variableEntries.map(([varName, value]) => (
                            <div
                                key={varName}
                                className="flex items-center gap-2 text-xs"
                            >
                                <Badge
                                    variant="secondary"
                                    className="font-mono text-[10px] shrink-0"
                                >
                                    {`{{${varName}}}`}
                                </Badge>
                                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                                <span className="text-muted-foreground truncate">
                                    {value || "—"}
                                </span>
                            </div>
                        ))}
                    </div>
                </CollapsibleSection>
            )}

            {/* Simulated transcript */}
            {result.simulated_transcript.length > 0 && (
                <CollapsibleSection
                    title="Simulated Conversation"
                    count={result.simulated_transcript.length}
                    suffix="turns"
                    expanded={expandedSections.has("transcript")}
                    onToggle={() => toggle("transcript")}
                >
                    <div className="space-y-2">
                        {result.simulated_transcript.map((turn, i) => (
                            <div
                                key={i}
                                className={`flex gap-2 text-xs ${turn.role === "assistant" ? "" : "flex-row-reverse"
                                    }`}
                            >
                                <div
                                    className={`rounded-lg px-3 py-2 max-w-[85%] ${turn.role === "assistant"
                                        ? "bg-primary/10 text-foreground"
                                        : "bg-muted text-foreground"
                                        }`}
                                >
                                    <span className="block text-[10px] font-medium text-muted-foreground mb-0.5">
                                        {turn.role === "assistant" ? agentName : "Caller"}
                                    </span>
                                    {turn.content}
                                </div>
                            </div>
                        ))}
                    </div>
                </CollapsibleSection>
            )}

            {/* Extracted data */}
            {extractionEntries.length > 0 && (
                <CollapsibleSection
                    title="Extracted Data"
                    count={extractionEntries.length}
                    suffix="fields"
                    expanded={expandedSections.has("extraction")}
                    onToggle={() => toggle("extraction")}
                >
                    <div className="grid gap-1">
                        {extractionEntries.map(([field, value]) => (
                            <div
                                key={field}
                                className="flex items-start gap-2 text-xs"
                            >
                                <span className="font-mono font-medium shrink-0 text-muted-foreground">
                                    {field}:
                                </span>
                                <span className="text-foreground break-all">
                                    {typeof value === "object"
                                        ? JSON.stringify(value)
                                        : String(value ?? "null")}
                                </span>
                            </div>
                        ))}
                    </div>
                </CollapsibleSection>
            )}

            <Separator />

            {/* CRM Write-back preview */}
            <CollapsibleSection
                title="CRM Write-Back Preview"
                count={writebackEntries.length}
                suffix="fields"
                expanded={expandedSections.has("writeback")}
                onToggle={() => toggle("writeback")}
            >
                {writebackEntries.length > 0 ? (
                    <div className="grid gap-1">
                        {writebackEntries.map(([crmField, value]) => (
                            <div
                                key={crmField}
                                className="flex items-center gap-2 text-xs"
                            >
                                <span className="font-medium shrink-0">{crmField}</span>
                                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                                <span className="text-muted-foreground break-all">
                                    {typeof value === "object"
                                        ? JSON.stringify(value)
                                        : String(value ?? "null")}
                                </span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        No write-back mappings configured or no matching extracted data.
                    </p>
                )}
            </CollapsibleSection>

            {/* Rendered prompt (collapsed by default) */}
            {result.rendered_prompt && (
                <CollapsibleSection
                    title="Rendered Prompt"
                    expanded={expandedSections.has("prompt")}
                    onToggle={() => toggle("prompt")}
                >
                    <pre className="rounded bg-muted px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                        {result.rendered_prompt}
                    </pre>
                </CollapsibleSection>
            )}
        </div>
    );
}

// ─── Collapsible Section Helper ──────────────────────────────────────────────

function CollapsibleSection({
    title,
    count,
    suffix = "items",
    expanded,
    onToggle,
    children,
}: {
    title: string;
    count?: number;
    suffix?: string;
    expanded: boolean;
    onToggle: () => void;
    children: React.ReactNode;
}) {
    return (
        <div>
            <button
                type="button"
                onClick={onToggle}
                className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors w-full"
            >
                {expanded ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                )}
                {title}
                {count !== undefined && (
                    <span className="text-[10px] text-muted-foreground">
                        ({count} {suffix})
                    </span>
                )}
            </button>
            {expanded && <div className="mt-2 ml-5">{children}</div>}
        </div>
    );
}
