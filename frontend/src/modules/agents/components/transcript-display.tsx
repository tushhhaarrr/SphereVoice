"use client";

/**
 * TranscriptDisplay — Real-time transcript viewer for test calls.
 *
 * Displays a scrolling list of transcript entries with:
 * - Speaker labels (AI / User) with distinct styling
 * - Timestamps relative to call start
 * - Auto-scroll to latest entry
 * - Visual distinction between speakers
 *
 * Receives transcript entries from the parent component
 * (populated via LiveKit data channel in use-test-call hook).
 */

import { useEffect, useRef } from "react";
import { Bot, User, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

// ── Types ───────────────────────────────────────────────────

export interface TranscriptEntry {
    /** Unique ID for React key */
    id: string;
    /** "ai" or "user" */
    speaker: "ai" | "user";
    /** The transcribed / generated text */
    text: string;
    /** ISO timestamp */
    timestamp: string;
    /** Whether this entry is still being streamed (partial) */
    isFinal: boolean;
    /** Optional: indicates this is a simulated (dry-run) tool call */
    isDryRun?: boolean;
    /** Optional: tool name if this entry represents a tool call */
    toolName?: string;
}

interface TranscriptDisplayProps {
    entries: TranscriptEntry[];
    /** Call start time — used to compute relative timestamps */
    callStartTime: number | null;
    /** Maximum height of the transcript area */
    maxHeight?: string;
}

// ── Helpers ─────────────────────────────────────────────────

function formatRelativeTime(timestamp: string, startTime: number | null): string {
    if (!startTime) return "";
    const entryTime = new Date(timestamp).getTime();
    const elapsed = Math.max(0, Math.floor((entryTime - startTime) / 1000));
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

// ── Component ───────────────────────────────────────────────

export function TranscriptDisplay({
    entries,
    callStartTime,
    maxHeight = "300px",
}: TranscriptDisplayProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new entries arrive
    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [entries]);

    if (entries.length === 0) {
        return (
            <div className="rounded-md border border-dashed border-muted-foreground/30 p-4 text-center">
                <p className="text-xs text-muted-foreground">
                    Waiting for conversation to begin...
                </p>
            </div>
        );
    }

    return (
        <ScrollArea
            className="rounded-md border bg-muted/30"
            style={{ maxHeight, height: maxHeight === "100%" ? "100%" : undefined }}
        >
            <div ref={scrollRef} className="space-y-2 p-3">
                {entries.map((entry) => (
                    <TranscriptBubble
                        key={entry.id}
                        entry={entry}
                        callStartTime={callStartTime}
                    />
                ))}
                <div ref={bottomRef} />
            </div>
        </ScrollArea>
    );
}

// ── Bubble Component ────────────────────────────────────────

function TranscriptBubble({
    entry,
    callStartTime,
}: {
    entry: TranscriptEntry;
    callStartTime: number | null;
}) {
    const isAI = entry.speaker === "ai";
    const isToolCall = !!entry.toolName;
    const relTime = formatRelativeTime(entry.timestamp, callStartTime);

    return (
        <div
            className={`flex gap-2 ${isAI ? "flex-row" : "flex-row-reverse"}`}
        >
            {/* Avatar */}
            <div
                className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full ${isToolCall
                        ? "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300"
                        : isAI
                            ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                            : "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                    }`}
            >
                {isToolCall ? <Wrench className="h-3.5 w-3.5" /> : isAI ? <Bot className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
            </div>

            {/* Content */}
            <div
                className={`flex max-w-[80%] flex-col ${isAI ? "items-start" : "items-end"
                    }`}
            >
                <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="text-[10px] font-medium uppercase text-muted-foreground">
                        {isToolCall ? entry.toolName : isAI ? "Agent" : "You"}
                    </span>
                    {entry.isDryRun && (
                        <Badge variant="outline" className="text-[9px] px-1 py-0 border-orange-300 text-orange-600 dark:border-orange-700 dark:text-orange-400">
                            Simulated
                        </Badge>
                    )}
                    {relTime && (
                        <span className="text-[10px] text-muted-foreground/60 font-mono">
                            {relTime}
                        </span>
                    )}
                </div>
                <div
                    className={`rounded-lg px-3 py-1.5 text-sm whitespace-pre-wrap ${isToolCall
                            ? "bg-orange-50 text-orange-900 dark:bg-orange-950 dark:text-orange-100 border border-orange-200 dark:border-orange-800"
                            : isAI
                                ? "bg-blue-50 text-blue-900 dark:bg-blue-950 dark:text-blue-100"
                                : "bg-green-50 text-green-900 dark:bg-green-950 dark:text-green-100"
                        } ${!entry.isFinal ? "opacity-70 italic" : ""}`}
                >
                    {entry.text}
                    {!entry.isFinal && (
                        <span className="ml-1 inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                    )}
                </div>
            </div>
        </div>
    );
}
