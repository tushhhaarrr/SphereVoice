/**
 * Live Calls WebSocket Hook — Connects to the backend WS endpoint
 * for real-time call monitoring updates.
 *
 * Handles:
 * - JWT authentication via query param
 * - Auto-reconnect with exponential backoff
 * - call_started, call_ended, call_updated, transcript_update events
 * - End-call action (sends end_call to server)
 * - Tenant subscription for admin/employee users
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CallMetrics,
  LiveCall,
  LiveEvent,
  LiveMetrics,
  TranscriptEntry,
  WebSocketStatus,
} from "@/modules/live/types";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:2998";
const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

interface UseLiveCallsReturn {
  calls: LiveCall[];
  metrics: LiveMetrics;
  wsStatus: WebSocketStatus;
  selectedCall: LiveCall | null;
  selectCall: (callId: string | null) => void;
  endCall: (callId: string) => void;
  reconnect: () => void;
}

const DEFAULT_METRICS: LiveMetrics = {
  activeCalls: 0,
  totalCallsToday: 0,
  avgDuration: 0,
  avgLatencyMs: 0,
};

const DEFAULT_CALL_METRICS: CallMetrics = {
  latencyMs: 0,
  turnCount: 0,
  functionCalls: 0,
};

async function getAuthToken(): Promise<string | null> {
  try {
    const { getSession } = await import("next-auth/react");
    const session = await getSession();
    const token = (session as unknown as Record<string, unknown> | null)?.accessToken;
    return (token as string) ?? null;
  } catch {
    return null;
  }
}

/**
 * Hook for real-time live call monitoring via WebSocket.
 */
export function useLiveCalls(): UseLiveCallsReturn {
  const [calls, setCalls] = useState<LiveCall[]>([]);
  const [metrics, setMetrics] = useState<LiveMetrics>(DEFAULT_METRICS);
  const [wsStatus, setWsStatus] = useState<WebSocketStatus>("disconnected");
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectRef = useRef<(() => Promise<void>) | null>(null);

  const handleEvent = useCallback((event: LiveEvent) => {
    const data = event.data;

    switch (event.event) {
      case "call_started": {
        const newCall: LiveCall = {
          callId: String(data.call_id ?? ""),
          tenantId: data.tenant_id as string | undefined,
          agentId: String(data.agent_id ?? ""),
          agentName: String(data.agent_name ?? data.agent_id ?? ""),
          callerNumber: String(data.from_number ?? ""),
          calledNumber: String(data.to_number ?? ""),
          direction: (data.direction as "inbound" | "outbound") ?? "inbound",
          duration: 0,
          status: "active",
          startedAt: String(data.started_at ?? new Date().toISOString()),
          sentiment: null,
          lastTranscript: null,
          transcript: [],
          metrics: { ...DEFAULT_CALL_METRICS },
        };
        setCalls((prev) => [...prev, newCall]);
        break;
      }

      case "call_updated": {
        const callId = String(data.call_id ?? "");
        setCalls((prev) =>
          prev.map((c) => {
            if (c.callId !== callId) return c;
            return {
              ...c,
              status: (data.status as LiveCall["status"]) ?? c.status,
              duration: (data.duration as number) ?? c.duration,
              sentiment: (data.sentiment as LiveCall["sentiment"]) ?? c.sentiment,
              metrics: {
                latencyMs: (data.latency_ms as number) ?? c.metrics.latencyMs,
                turnCount: (data.turn_count as number) ?? c.metrics.turnCount,
                functionCalls: (data.function_calls as number) ?? c.metrics.functionCalls,
              },
            };
          })
        );
        break;
      }

      case "call_ended": {
        const endedId = String(data.call_id ?? "");
        setCalls((prev) => prev.filter((c) => c.callId !== endedId));
        break;
      }

      case "transcript_update": {
        const tCallId = String(data.call_id ?? "");
        const entry: TranscriptEntry = {
          speaker: (data.speaker as "user" | "assistant") ?? "user",
          text: String(data.text ?? ""),
          timestamp: String(data.timestamp ?? new Date().toISOString()),
          confidence: data.confidence as number | undefined,
        };
        setCalls((prev) =>
          prev.map((c) => {
            if (c.callId !== tCallId) return c;
            return {
              ...c,
              lastTranscript: entry.text,
              transcript: [...c.transcript, entry],
            };
          })
        );
        break;
      }

      case "metrics_update": {
        if ("activeCalls" in data || "active_calls" in data) {
          setMetrics({
            activeCalls: (data.active_calls as number) ?? (data.activeCalls as number) ?? 0,
            totalCallsToday: (data.total_calls_today as number) ?? (data.totalCallsToday as number) ?? 0,
            avgDuration: (data.avg_duration as number) ?? (data.avgDuration as number) ?? 0,
            avgLatencyMs: (data.avg_latency_ms as number) ?? (data.avgLatencyMs as number) ?? 0,
          });
        }
        break;
      }

      case "ping":
      case "subscribed":
        break;
    }
  }, []);

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setWsStatus("connecting");

    const token = await getAuthToken();
    if (!token) {
      setWsStatus("error");
      return;
    }

    try {
      const url = `${WS_BASE}/ws/live-calls?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("connected");
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const liveEvent = JSON.parse(event.data as string) as LiveEvent;
          handleEvent(liveEvent);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        setWsStatus("error");
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        wsRef.current = null;

        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts.current += 1;
          const delay =
            RECONNECT_DELAY_MS * Math.pow(1.5, reconnectAttempts.current - 1);
          reconnectTimer.current = setTimeout(() => {
            void connectRef.current?.();
          }, delay);
        }
      };
    } catch {
      setWsStatus("error");
    }
  }, [handleEvent]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const endCall = useCallback((callId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ action: "end_call", call_id: callId })
      );
    }
  }, []);

  const selectCall = useCallback((callId: string | null) => {
    setSelectedCallId(callId);
  }, []);

  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    reconnectAttempts.current = 0;
    void connectRef.current?.();
  }, []);

  useEffect(() => {
    void connectRef.current?.();
    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const selectedCall = selectedCallId
    ? calls.find((c) => c.callId === selectedCallId) ?? null
    : null;

  return { calls, metrics, wsStatus, selectedCall, selectCall, endCall, reconnect };
}
