"use client";

import { Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTestScenario } from "../../hooks/use-test-scenarios";
import { useTestCall } from "../../hooks/use-test-call";
import { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { TranscriptDisplay } from "../transcript-display";

interface RunScenarioProps {
    agentId: string;
    scenarioId: string;
    agentVersion?: number | null;
}

export function RunScenario({ agentId, scenarioId, agentVersion }: RunScenarioProps) {
    const scenario = useTestScenario(agentId, scenarioId);
    const testCall = useTestCall(agentId);
    const [showTranscript, setShowTranscript] = useState(false);

    const handleRun = async () => {
        const vars = scenario.data?.dynamic_variables ?? {};
        // Convert all values to strings for dynamic_variables
        const stringVars: Record<string, string> = {};
        for (const [k, v] of Object.entries(vars)) {
            stringVars[k] = String(v);
        }

        const extraBody: Record<string, unknown> = {
            scenario_id: scenarioId,
        };
        if (agentVersion != null) {
            extraBody.agent_version = agentVersion;
        }

        await testCall.startCall(stringVars, extraBody);
        setShowTranscript(true);
    };

    const isRunning = testCall.status === "connecting";

    return (
        <>
            <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                onClick={handleRun}
                disabled={isRunning}
                title="Run scenario"
            >
                {isRunning ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                    <Play className="h-3.5 w-3.5" />
                )}
            </Button>

            <Dialog open={showTranscript} onOpenChange={setShowTranscript}>
                <DialogContent className="max-w-lg max-h-[80vh]">
                    <DialogHeader>
                        <DialogTitle className="text-sm">Test Call Transcript</DialogTitle>
                    </DialogHeader>
                    <TranscriptDisplay
                        entries={testCall.transcript}
                        callStartTime={testCall.callStartTime}
                        maxHeight="400px"
                    />
                    {testCall.status === "ended" && (
                        <p className="text-xs text-muted-foreground text-center mt-2">
                            Call ended. Results will appear in scenario history after processing.
                        </p>
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
}
