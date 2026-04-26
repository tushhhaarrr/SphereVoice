"use client";

/**
 * Outbound Test Call Hook — Initiates a real phone call via Plivo
 * to test an agent over PSTN (instead of browser WebRTC).
 *
 * Uses POST /api/v1/calls (the outbound call endpoint) and polls
 * call status to track progress.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchWithAuth } from "@/lib/api-client";

export type OutboundTestCallStatus =
    | "idle"
    | "dialing"
    | "ringing"
    | "in-progress"
    | "completed"
    | "failed";

export interface OutboundTestCallState {
    status: OutboundTestCallStatus;
    callId: string | null;
    duration: number;
    error: string | null;
}

interface OutboundTestCallActions {
    startCall: (fromNumber: string, toNumber: string) => Promise<void>;
    endCall: () => Promise<void>;
}

export function useOutboundTestCall(
    agentId: string,
): OutboundTestCallState & OutboundTestCallActions {
    const [state, setState] = useState<OutboundTestCallState>({
        status: "idle",
        callId: null,
        duration: 0,
        error: null,
    });

    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const callStartRef = useRef<number | null>(null);

    // Clean up on unmount
    useEffect(() => {
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
            if (pollerRef.current) clearInterval(pollerRef.current);
        };
    }, []);

    // Poll call status when active
    useEffect(() => {
        if (!state.callId || state.status === "completed" || state.status === "failed" || state.status === "idle") {
            if (pollerRef.current) {
                clearInterval(pollerRef.current);
                pollerRef.current = null;
            }
            return;
        }

        const poll = async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/calls/${state.callId}`);
                if (!res.ok) return;

                const call: { status: string; disconnection_reason?: string | null; duration_seconds?: number | null } =
                    await res.json();

                if (call.status === "in-progress" || call.status === "in_progress") {
                    setState((prev) => ({ ...prev, status: "in-progress" }));
                } else if (call.status === "completed") {
                    if (timerRef.current) {
                        clearInterval(timerRef.current);
                        timerRef.current = null;
                    }
                    setState((prev) => ({
                        ...prev,
                        status: "completed",
                        duration: call.duration_seconds ?? prev.duration,
                    }));
                } else if (call.status === "failed") {
                    if (timerRef.current) {
                        clearInterval(timerRef.current);
                        timerRef.current = null;
                    }
                    setState((prev) => ({
                        ...prev,
                        status: "failed",
                        error: call.disconnection_reason ?? "Call failed",
                    }));
                }
            } catch {
                // Ignore polling errors
            }
        };

        void poll();
        pollerRef.current = setInterval(() => void poll(), 2000);

        return () => {
            if (pollerRef.current) {
                clearInterval(pollerRef.current);
                pollerRef.current = null;
            }
        };
    }, [state.callId, state.status]);

    const startCall = useCallback(
        async (fromNumber: string, toNumber: string) => {
            if (state.status !== "idle" && state.status !== "completed" && state.status !== "failed") return;

            setState({ status: "dialing", callId: null, duration: 0, error: null });

            try {
                const res = await fetchWithAuth("/api/v1/calls", {
                    method: "POST",
                    body: JSON.stringify({
                        agent_id: agentId,
                        to_number: toNumber,
                        from_number: fromNumber,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json().catch(() => null);
                    throw new Error(
                        (err as Record<string, string> | null)?.detail ?? `Failed to initiate call (${res.status})`,
                    );
                }

                const data: { call_id: string; status: string; started_at: string } = await res.json();

                callStartRef.current = Date.now();
                setState((prev) => ({
                    ...prev,
                    status: "ringing",
                    callId: data.call_id,
                }));

                // Start duration timer
                timerRef.current = setInterval(() => {
                    if (callStartRef.current) {
                        setState((prev) => ({
                            ...prev,
                            duration: Math.floor((Date.now() - callStartRef.current!) / 1000),
                        }));
                    }
                }, 1000);
            } catch (err) {
                setState({
                    status: "failed",
                    callId: null,
                    duration: 0,
                    error: err instanceof Error ? err.message : "Failed to start outbound call",
                });
            }
        },
        [agentId, state.status],
    );

    const endCall = useCallback(async () => {
        if (!state.callId) return;

        try {
            await fetchWithAuth(`/api/v1/calls/${state.callId}/end`, { method: "POST" });
        } catch {
            // Best effort
        }

        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }
        if (pollerRef.current) {
            clearInterval(pollerRef.current);
            pollerRef.current = null;
        }

        setState((prev) => ({ ...prev, status: "completed" }));
    }, [state.callId]);

    return { ...state, startCall, endCall };
}
