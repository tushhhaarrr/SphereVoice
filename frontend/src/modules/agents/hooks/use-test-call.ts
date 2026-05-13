/**
 * Test Call Hook â€” WebRTC connection to LiveKit for browser-based agent testing.
 *
 * Manages the lifecycle of a test call:
 * 1. Request a test room from the backend API
 * 2. Connect to LiveKit via WebRTC using livekit-client
 * 3. Handle audio I/O (mic â†’ LiveKit â†’ pipeline â†’ LiveKit â†’ speaker)
 * 4. Receive real-time transcript updates via LiveKit data channel
 * 5. Disconnect and clean up on call end
 *
 * Phase 6: Full connection + real-time transcript display.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  ConnectionState,
  Track,
  DataPacket_Kind,
  type RemoteTrack,
  type RemoteTrackPublication,
  type RemoteParticipant,
} from "livekit-client";
import type { TranscriptEntry } from "@/modules/agents";

export type TestCallStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "disconnecting"
  | "ended"
  | "error";

export interface TestCallState {
  status: TestCallStatus;
  duration: number;
  error: string | null;
  roomName: string | null;
  participantCount: number;
  callId: string | null;
  transcript: TranscriptEntry[];
  callStartTime: number | null;
  latency: TestCallLatencyState;
}

export interface TestCallServiceLatency {
  stage: "stt" | "llm" | "tts";
  label: string;
  responseLatencyMs: number | null;
  processingLatencyMs: number | null;
  ttfbLatencyMs: number | null;
  processor: string | null;
  model: string | null;
}

export interface TestCallLatencyState {
  turnId: number | null;
  updatedAt: string | null;
  pipelineE2eLatencyMs: number | null;
  services: {
    stt: TestCallServiceLatency;
    llm: TestCallServiceLatency;
    tts: TestCallServiceLatency;
  };
}

interface TestCallActions {
  startCall: (dynamicVariables?: Record<string, string>, extraBody?: Record<string, unknown>) => Promise<void>;
  endCall: () => Promise<void>;
  toggleMute: () => void;
  isMuted: boolean;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:2998").replace(/\/api\/v1\/?$/, "");

/** Counter for generating unique transcript entry IDs */
let transcriptCounter = 0;

const DEFAULT_LATENCY_STATE: TestCallLatencyState = {
  turnId: null,
  updatedAt: null,
  pipelineE2eLatencyMs: null,
  services: {
    stt: {
      stage: "stt",
      label: "STT",
      responseLatencyMs: null,
      processingLatencyMs: null,
      ttfbLatencyMs: null,
      processor: null,
      model: null,
    },
    llm: {
      stage: "llm",
      label: "LLM",
      responseLatencyMs: null,
      processingLatencyMs: null,
      ttfbLatencyMs: null,
      processor: null,
      model: null,
    },
    tts: {
      stage: "tts",
      label: "TTS",
      responseLatencyMs: null,
      processingLatencyMs: null,
      ttfbLatencyMs: null,
      processor: null,
      model: null,
    },
  },
};

async function ensureMicrophonePermission(): Promise<void> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone capture is not supported in this browser.");
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
  } catch (error) {
    if (error instanceof DOMException) {
      if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        throw new Error(
          "Microphone access is required for Test Audio. Allow microphone access in your browser and try again.",
        );
      }

      if (error.name === "NotFoundError") {
        throw new Error("No microphone was found. Connect a microphone and try again.");
      }
    }

    throw new Error("Unable to access the microphone. Check browser permissions and try again.");
  }
}

/**
 * Hook for managing a test call session via LiveKit WebRTC.
 *
 * @param agentId - The agent to test
 * @returns State object + action handlers
 */
export function useTestCall(agentId: string): TestCallState & TestCallActions {
  const [state, setState] = useState<TestCallState>({
    status: "idle",
    duration: 0,
    error: null,
    roomName: null,
    participantCount: 0,
    callId: null,
    transcript: [],
    callStartTime: null,
    latency: DEFAULT_LATENCY_STATE,
  });
  const [isMuted, setIsMuted] = useState(false);

  const roomRef = useRef<Room | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const callStatusPollerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      if (callStatusPollerRef.current) {
        clearInterval(callStatusPollerRef.current);
        callStatusPollerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!state.callId || (state.status !== "connecting" && state.status !== "connected")) {
      if (callStatusPollerRef.current) {
        clearInterval(callStatusPollerRef.current);
        callStatusPollerRef.current = null;
      }
      return;
    }

    const pollCallState = async () => {
      try {
        const { getSession } = await import("next-auth/react");
        const session = await getSession();
        const headers: Record<string, string> = {};
        if (session?.accessToken) {
          headers.Authorization = `Bearer ${session.accessToken}`;
        }

        const response = await fetch(`${API_BASE}/api/v1/calls/${state.callId}`, {
          headers,
        });
        if (!response.ok) return;

        const call: {
          status: string;
          disconnection_reason?: string | null;
        } = await response.json();

        if (call.status === "completed" || call.status === "failed") {
          const message = call.status === "failed"
            ? (call.disconnection_reason || "The voice pipeline failed before the conversation started.")
            : (call.disconnection_reason || "Call ended.");

          if (roomRef.current) {
            roomRef.current.disconnect();
            roomRef.current = null;
          }

          if (audioRef.current) {
            audioRef.current.srcObject = null;
            audioRef.current.remove();
            audioRef.current = null;
          }

          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }

          if (callStatusPollerRef.current) {
            clearInterval(callStatusPollerRef.current);
            callStatusPollerRef.current = null;
          }

          setState((prev) => ({
            ...prev,
            status: call.status === "completed" ? "ended" : "error",
            error: call.status === "failed" ? message : prev.error,
          }));
        }
      } catch {
        // Ignore polling errors and keep the session alive.
      }
    };

    void pollCallState();
    callStatusPollerRef.current = setInterval(() => {
      void pollCallState();
    }, 1500);

    return () => {
      if (callStatusPollerRef.current) {
        clearInterval(callStatusPollerRef.current);
        callStatusPollerRef.current = null;
      }
    };
  }, [state.callId, state.status]);

  const startCall = useCallback(async (dynamicVariables?: Record<string, string>, extraBody?: Record<string, unknown>) => {
    if (state.status !== "idle" && state.status !== "error" && state.status !== "ended") return;

    setState((prev) => ({
      ...prev,
      status: "connecting",
      error: null,
      duration: 0,
      transcript: [],
      callStartTime: null,
      callId: null,
      latency: DEFAULT_LATENCY_STATE,
    }));

    try {
      await ensureMicrophonePermission();

      // 1. Request test room from backend (with JWT auth)
      const { getSession } = await import("next-auth/react");
      const session = await getSession();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (session?.accessToken) {
        headers["Authorization"] = `Bearer ${session.accessToken}`;
      }

      const body: Record<string, unknown> = { agent_id: agentId };
      if (dynamicVariables && Object.keys(dynamicVariables).length > 0) {
        body.dynamic_variables = dynamicVariables;
      }
      if (extraBody) {
        Object.assign(body, extraBody);
      }

      const response = await fetch(`${API_BASE}/api/v1/calls/test`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(
          errorData?.detail ?? `Failed to create test call (${response.status})`
        );
      }

      const data: {
        token: string;
        room_name: string;
        call_id: string;
        livekit_url: string;
      } = await response.json();

      const livekitUrl = data.livekit_url || (process.env.NEXT_PUBLIC_LIVEKIT_URL ?? "wss://localhost:7880");

      // 2. Create LiveKit room and connect
      // Disconnect stale room from a previous call if it somehow survived
      if (roomRef.current) {
        roomRef.current.removeAllListeners();
        roomRef.current.disconnect();
        roomRef.current = null;
      }
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
          channelCount: 1,
        },
      });

      roomRef.current = room;
      const callStartTimestamp = Date.now();

      // 3. Set up event handlers
      room.on(RoomEvent.ConnectionStateChanged, (connectionState: ConnectionState) => {
        if (connectionState === ConnectionState.Connected) {
          setState((prev) => ({
            ...prev,
            status: "connected",
            roomName: data.room_name,
            callId: data.call_id,
            callStartTime: callStartTimestamp,
            participantCount: room.remoteParticipants.size + 1,
          }));
        } else if (connectionState === ConnectionState.Disconnected) {
          // Server-side hangup (end_on_silence, max_duration, agent end_call, etc.)
          // Go to "ended" so the UI clearly shows the call has finished â€”
          // the user won't keep talking into dead air.
          if (roomRef.current === room) {
            room.removeAllListeners();
            roomRef.current = null;
          }
          if (audioRef.current) {
            audioRef.current.srcObject = null;
            audioRef.current.remove();
            audioRef.current = null;
          }
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
          if (callStatusPollerRef.current) {
            clearInterval(callStatusPollerRef.current);
            callStatusPollerRef.current = null;
          }
          // Keep duration + transcript visible so the user can review the session.
          setState((prev) => ({
            ...prev,
            status: "ended",
            roomName: null,
            participantCount: 0,
          }));
        }
      });

      room.on(RoomEvent.TrackSubscribed, (
        track: RemoteTrack,
        _publication: RemoteTrackPublication,
        participant: RemoteParticipant,
      ) => {
        // Guard: ignore if room is already disconnected or participant left
        if (roomRef.current !== room || !room.remoteParticipants.has(participant.identity)) {
          return;
        }
        // Attach remote audio (agent's TTS output) to an audio element
        if (track.kind === Track.Kind.Audio) {
          if (!audioRef.current) {
            audioRef.current = document.createElement("audio");
            audioRef.current.autoplay = true;
            document.body.appendChild(audioRef.current);
          }
          const mediaTrack = track.mediaStreamTrack;
          if (mediaTrack) {
            const stream = new MediaStream([mediaTrack]);
            audioRef.current.srcObject = stream;
            void audioRef.current.play().catch(() => {
              // Ignore autoplay failures; the user can still interact with the page.
            });
          }
        }
      });

      room.on(RoomEvent.ParticipantConnected, () => {
        setState((prev) => ({
          ...prev,
          participantCount: room.remoteParticipants.size + 1,
        }));
      });

      room.on(RoomEvent.ParticipantDisconnected, () => {
        setState((prev) => ({
          ...prev,
          participantCount: Math.max(0, room.remoteParticipants.size),
        }));
      });

      // 4. Listen for data channel messages (transcript updates)
      room.on(RoomEvent.DataReceived, (
        payload: Uint8Array,
        participant?: RemoteParticipant,
        _kind?: DataPacket_Kind,
      ) => {
        try {
          const text = new TextDecoder().decode(payload);
          const message = JSON.parse(text) as {
            type: string;
            speaker?: "ai" | "user";
            text?: string;
            is_final?: boolean;
            timestamp?: string;
            entry_id?: string;
            turn_id?: number;
            pipeline?: { e2e_latency_ms?: number | null };
            services?: Record<string, {
              stage?: "stt" | "llm" | "tts";
              label?: string;
              response_latency_ms?: number | null;
              processing_latency_ms?: number | null;
              ttfb_latency_ms?: number | null;
              processor?: string | null;
              model?: string | null;
            }>;
          };

          if (message.type === "transcript_update" && message.text) {
            const entryId = message.entry_id || `t_${++transcriptCounter}`;
            const entry: TranscriptEntry = {
              id: entryId,
              speaker: message.speaker ?? "ai",
              text: message.text,
              timestamp: message.timestamp ?? new Date().toISOString(),
              isFinal: message.is_final ?? true,
            };

            setState((prev) => {
              // If this is an update to an existing partial entry, replace it
              const existingIndex = prev.transcript.findIndex(
                (e) => e.id === entryId
              );
              if (existingIndex >= 0) {
                const updated = [...prev.transcript];
                updated[existingIndex] = entry;
                return { ...prev, transcript: updated };
              }
              // Otherwise append
              return {
                ...prev,
                transcript: [...prev.transcript, entry],
              };
            });
          } else if (message.type === "latency_update") {
            setState((prev) => ({
              ...prev,
              latency: {
                turnId: message.turn_id ?? null,
                updatedAt: message.timestamp ?? new Date().toISOString(),
                pipelineE2eLatencyMs: message.pipeline?.e2e_latency_ms ?? null,
                services: {
                  stt: parseLatencyService("stt", message.services?.stt),
                  llm: parseLatencyService("llm", message.services?.llm),
                  tts: parseLatencyService("tts", message.services?.tts),
                },
              },
            }));
          }
        } catch {
          // Ignore non-JSON data channel messages
        }
      });

      // 5. Connect to LiveKit
      await room.connect(livekitUrl, data.token);

      // 6. Publish local microphone track
      await room.localParticipant.setMicrophoneEnabled(true);

      // 7. Start duration timer
      timerRef.current = setInterval(() => {
        setState((prev) => ({
          ...prev,
          duration: Math.floor((Date.now() - callStartTimestamp) / 1000),
        }));
      }, 1000);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to start test call";
      setState((prev) => ({
        ...prev,
        status: "error",
        error: errorMessage,
      }));

      // Clean up on error
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
    }
  }, [agentId, state.status]);

  const endCall = useCallback(async () => {
    setState((prev) => ({ ...prev, status: "disconnecting" }));

    try {
      if (roomRef.current) {
        roomRef.current.removeAllListeners();
        roomRef.current.disconnect();
        roomRef.current = null;
      }

      // Clean up audio element
      if (audioRef.current) {
        audioRef.current.srcObject = null;
        audioRef.current.remove();
        audioRef.current = null;
      }

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      if (callStatusPollerRef.current) {
        clearInterval(callStatusPollerRef.current);
        callStatusPollerRef.current = null;
      }
    } finally {
      setState((prev) => ({
        ...prev,
        status: "idle",
        duration: 0,
        error: null,
        roomName: null,
        participantCount: 0,
        // Keep transcript and callStartTime so user can review after call
      }));
      setIsMuted(false);
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (roomRef.current?.localParticipant) {
      const newMuted = !isMuted;
      roomRef.current.localParticipant.setMicrophoneEnabled(!newMuted);
      setIsMuted(newMuted);
    }
  }, [isMuted]);

  return {
    ...state,
    startCall,
    endCall,
    toggleMute,
    isMuted,
  };
}

function parseLatencyService(
  stage: "stt" | "llm" | "tts",
  service:
    | {
      stage?: "stt" | "llm" | "tts";
      label?: string;
      response_latency_ms?: number | null;
      processing_latency_ms?: number | null;
      ttfb_latency_ms?: number | null;
      processor?: string | null;
      model?: string | null;
    }
    | undefined,
): TestCallServiceLatency {
  const defaultService = DEFAULT_LATENCY_STATE.services[stage];
  if (!service) {
    return defaultService;
  }

  return {
    stage,
    label: service.label ?? defaultService.label,
    responseLatencyMs: service.response_latency_ms ?? null,
    processingLatencyMs: service.processing_latency_ms ?? null,
    ttfbLatencyMs: service.ttfb_latency_ms ?? null,
    processor: service.processor ?? null,
    model: service.model ?? null,
  };
}

