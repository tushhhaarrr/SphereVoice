"use client";

import { useMemo } from "react";
import {
    ArrowRight,
    Headset,
    Loader2,
    Mic,
    MicOff,
    Phone,
    PhoneOff,
    Radio,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
    useTestCall,
    TranscriptDisplay,
    type TestCallStatus,
} from "@/modules/agents";
import { useCampaign, useCampaignContact } from "../../hooks/use-campaigns";

interface ContactTestCallDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    campaignId: string;
    tenantId?: string;
    contactId: string;
}

function formatDuration(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

const STATUS_LABEL: Record<TestCallStatus, string> = {
    idle: "Ready",
    connecting: "Connecting…",
    connected: "In Call",
    disconnecting: "Ending…",
    ended: "Call Ended",
    error: "Error",
};

const STATUS_COLOR: Record<TestCallStatus, string> = {
    idle: "bg-gray-100 text-gray-700",
    connecting: "bg-yellow-100 text-yellow-700",
    connected: "bg-green-100 text-green-700",
    disconnecting: "bg-orange-100 text-orange-700",
    ended: "bg-slate-100 text-slate-600",
    error: "bg-red-100 text-red-700",
};

export function ContactTestCallDialog({
    open,
    onOpenChange,
    campaignId,
    tenantId,
    contactId,
}: ContactTestCallDialogProps) {
    const campaign = useCampaign(campaignId, tenantId);
    const contact = useCampaignContact(campaignId, contactId, tenantId);

    const agentId = campaign.data?.agent_id ?? "";
    const testCall = useTestCall(agentId);

    // Build dynamic variables from contact_data + variable_mapping
    const resolvedVariables = useMemo(() => {
        if (!campaign.data || !contact.data) return {};
        const variableMapping = campaign.data.variable_mapping ?? {};
        const contactData = contact.data.contact_data ?? {};
        const vars: Record<string, string> = {};

        for (const [varName, crmField] of Object.entries(variableMapping)) {
            const val = contactData[crmField];
            if (val !== undefined && val !== null) {
                vars[varName] = String(val);
            }
        }

        // Always inject CRM tracking context for writeback
        if (contact.data.crm_record_id) {
            vars["caller_crm_id"] = contact.data.crm_record_id;
        }
        if (contact.data.crm_module) {
            vars["caller_crm_module"] = contact.data.crm_module;
        }

        return vars;
    }, [campaign.data, contact.data]);

    const variableEntries = Object.entries(resolvedVariables);

    // Auto-disconnect on dialog close
    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen && (testCall.status === "connected" || testCall.status === "connecting")) {
            testCall.endCall();
        }
        onOpenChange(nextOpen);
    };

    const handleStartCall = () => {
        testCall.startCall(resolvedVariables);
    };

    const isLoading = campaign.isLoading || contact.isLoading;
    const canStart = testCall.status === "idle" || testCall.status === "ended" || testCall.status === "error";
    const isActive = testCall.status === "connected" || testCall.status === "connecting";

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="max-w-2xl max-h-[85vh]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Headset className="h-5 w-5" />
                        Browser Test Call — {contact.data?.phone_number ?? "Loading…"}
                    </DialogTitle>
                    <DialogDescription>
                        Talk to the AI agent through your browser using this contact&apos;s
                        CRM data as variables. No phone call is made — audio goes through
                        your microphone and speakers.
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <ScrollArea className="max-h-[65vh] pr-2">
                        <div className="space-y-4">
                            {/* Injected variables preview */}
                            {variableEntries.length > 0 && (
                                <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                                    <p className="text-xs font-medium text-muted-foreground">
                                        Variables injected from CRM data ({variableEntries.length})
                                    </p>
                                    <div className="grid gap-1">
                                        {variableEntries.map(([varName, value]) => (
                                            <div key={varName} className="flex items-center gap-2 text-xs">
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
                                </div>
                            )}

                            {variableEntries.length === 0 && (
                                <div className="rounded-lg border border-dashed p-3 text-center">
                                    <p className="text-xs text-muted-foreground">
                                        No variable mapping configured in this campaign.
                                        The agent will use default variable values.
                                    </p>
                                </div>
                            )}

                            <Separator />

                            {/* Call controls */}
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Badge className={STATUS_COLOR[testCall.status]}>
                                        {testCall.status === "connecting" && (
                                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                                        )}
                                        {testCall.status === "connected" && (
                                            <Radio className="mr-1 h-3 w-3" />
                                        )}
                                        {STATUS_LABEL[testCall.status]}
                                    </Badge>
                                    {testCall.status === "connected" && (
                                        <span className="text-sm font-mono tabular-nums text-muted-foreground">
                                            {formatDuration(testCall.duration)}
                                        </span>
                                    )}
                                </div>

                                <div className="flex items-center gap-2">
                                    {isActive && (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8"
                                            onClick={testCall.toggleMute}
                                        >
                                            {testCall.isMuted ? (
                                                <MicOff className="h-4 w-4 text-destructive" />
                                            ) : (
                                                <Mic className="h-4 w-4" />
                                            )}
                                        </Button>
                                    )}

                                    {canStart && (
                                        <Button size="sm" onClick={handleStartCall}>
                                            <Phone className="mr-1.5 h-4 w-4" />
                                            {testCall.status === "ended" || testCall.status === "error"
                                                ? "Call Again"
                                                : "Start Call"}
                                        </Button>
                                    )}

                                    {isActive && (
                                        <Button
                                            variant="destructive"
                                            size="sm"
                                            onClick={() => testCall.endCall()}
                                        >
                                            <PhoneOff className="mr-1.5 h-4 w-4" />
                                            End Call
                                        </Button>
                                    )}
                                </div>
                            </div>

                            {/* Error message */}
                            {testCall.error && (
                                <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                                    {testCall.error}
                                </div>
                            )}

                            {/* Transcript */}
                            {testCall.transcript.length > 0 && (
                                <div className="space-y-2">
                                    <p className="text-xs font-medium text-muted-foreground">
                                        Live Transcript
                                    </p>
                                    <div className="rounded-lg border p-3 max-h-72 overflow-y-auto">
                                        <TranscriptDisplay
                                            entries={testCall.transcript}
                                            callStartTime={testCall.callStartTime}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* Contact data reference */}
                            {contact.data && Object.keys(contact.data.contact_data).length > 0 && (
                                <details className="group">
                                    <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                                        Full CRM Contact Data ({Object.keys(contact.data.contact_data).length} fields)
                                    </summary>
                                    <div className="mt-2 rounded-lg border bg-muted/20 p-3 max-h-48 overflow-y-auto">
                                        <div className="grid gap-1">
                                            {Object.entries(contact.data.contact_data).map(([k, v]) => (
                                                <div key={k} className="flex items-start gap-2 text-xs">
                                                    <span className="font-mono font-medium text-muted-foreground shrink-0">
                                                        {k}:
                                                    </span>
                                                    <span className="break-all">
                                                        {v !== null && v !== undefined ? String(v) : "—"}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </details>
                            )}
                        </div>
                    </ScrollArea>
                )}
            </DialogContent>
        </Dialog>
    );
}
