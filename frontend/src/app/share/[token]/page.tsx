"use client";

/**
 * Public Agent Demo Page — /share/[token]
 *
 * Uses @livekit/agents-ui AgentSessionView_01 block with the Aura
 * audio visualizer for a polished full-screen voice demo experience.
 */

import "@livekit/components-styles";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { RoomAudioRenderer, SessionProvider, useSession } from "@livekit/components-react";
import { TokenSource } from "livekit-client";
import { useTheme } from "next-themes";
import { AgentSessionView_01 } from "@/components/agents-ui/blocks/agent-session-view-01";

const API_BASE = "";

// Force dark mode for this page only, cooperating with next-themes ThemeProvider
function useForceDarkMode() {
  const { setTheme, theme } = useTheme();
  useEffect(() => {
    const previous = theme;
    setTheme("dark");
    return () => setTheme(previous ?? "light");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

// ── Types ────────────────────────────────────────────────────

interface ShareMeta {
  agent_id: string;
  agent_name: string;
  token: string;
  expires_at: string | null;
}

interface CallCredentials {
  call_id: string;
  token: string;
  room_name: string;
  livekit_url: string;
}

// ── Main page ─────────────────────────────────────────────────

export default function ShareDemoPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = React.use(params);
  useForceDarkMode();
  const [meta, setMeta] = useState<ShareMeta | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [callCreds, setCallCreds] = useState<CallCredentials | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [isEnded, setIsEnded] = useState(false);

  // 1. Resolve metadata on mount
  useEffect(() => {
    const resolveLink = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/share/${token}`);
        if (!res.ok) {
          const body = await res.json().catch(() => ({})) as { detail?: string };
          setLoadError(body.detail ?? "This link is not valid or has expired.");
          return;
        }
        const data = await res.json() as ShareMeta;
        setMeta(data);
      } catch {
        setLoadError("Unable to reach the server. Please try again later.");
      }
    };
    void resolveLink();
  }, [token]);

  // 2. Start call
  const handleStartCall = useCallback(async () => {
    if (!meta || isStarting) return;
    setIsStarting(true);
    setStartError(null);
    try {
      const visitorId = `visitor_${Math.random().toString(36).slice(2)}`;
      const res = await fetch(`${API_BASE}/api/v1/share/${token}/call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_id: visitorId }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        setStartError(body.detail ?? `Failed to start call (${res.status})`);
        return;
      }
      const creds = await res.json() as CallCredentials;
      setCallCreds(creds);
    } catch {
      setStartError("Failed to connect. Please try again.");
    } finally {
      setIsStarting(false);
    }
  }, [meta, isStarting, token]);

  // 3. Disconnect (called when session ends)
  const handleDisconnect = useCallback(() => {
    setCallCreds(null);
    setIsEnded(true);
  }, []);

  // ── Active call — full-screen LiveKit session ──────────────

  if (callCreds) {
    return (
      <ActiveCallView
        creds={callCreds}
        agentName={meta?.agent_name ?? ""}
        onDisconnect={handleDisconnect}
      />
    );
  }

  // ── Pre-call / error / ended states (card layout) ─────────

  if (loadError) {
    return (
      <DemoShell agentName="Agent Demo">
        <div className="flex flex-col items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/10 px-6 py-8 text-center">
          <span className="text-3xl">🔒</span>
          <p className="text-sm font-medium text-destructive">{loadError}</p>
        </div>
      </DemoShell>
    );
  }

  if (!meta) {
    return (
      <DemoShell agentName="Loading…">
        <div className="flex items-center justify-center py-12">
          <svg className="h-8 w-8 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
        </div>
      </DemoShell>
    );
  }

  if (isEnded) {
    return (
      <DemoShell agentName={meta.agent_name}>
        <div className="flex flex-col items-center gap-4 py-8 text-center">
          <span className="text-4xl">👋</span>
          <p className="text-lg font-semibold">Call ended</p>
          <p className="text-sm text-muted-foreground">Thanks for trying {meta.agent_name}!</p>
          <button
            onClick={() => { setIsEnded(false); setCallCreds(null); }}
            className="mt-2 rounded-full bg-primary px-6 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Call again
          </button>
        </div>
      </DemoShell>
    );
  }

  return (
    <DemoShell agentName={meta.agent_name} expiresAt={meta.expires_at}>
      <div className="flex flex-col items-center gap-6 py-8">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-primary/10 text-4xl">
          🎙️
        </div>
        <div className="text-center">
          <p className="font-semibold text-lg">Ready to talk?</p>
          <p className="text-sm text-muted-foreground mt-1">
            Click below to start a voice conversation with {meta.agent_name}.
          </p>
        </div>

        {startError && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {startError}
          </p>
        )}

        <button
          onClick={handleStartCall}
          disabled={isStarting}
          className="flex items-center gap-2 rounded-full bg-primary px-8 py-3 text-base font-semibold text-primary-foreground shadow-lg transition-all hover:bg-primary/90 hover:shadow-xl active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isStarting ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Connecting…
            </>
          ) : (
            <>
              <span>🎙️</span>
              Start Call
            </>
          )}
        </button>

        <p className="text-xs text-muted-foreground">
          Your browser will ask for microphone permission.
        </p>
      </div>
    </DemoShell>
  );
}

// ── Active call view (owns the LiveKit session lifecycle) ─────

function ActiveCallView({
  creds,
  agentName,
  onDisconnect,
}: {
  creds: CallCredentials;
  agentName: string;
  onDisconnect: () => void;
}) {
  const session = useSession(
    TokenSource.literal({ serverUrl: creds.livekit_url, participantToken: creds.token }),
  );
  const hasConnectedRef = useRef(false);

  // Connect on mount
  useEffect(() => {
    void session.start({ tracks: { microphone: { enabled: true } } });
    // session.start ref is stable; intentionally run once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Detect disconnect after the session was previously connected
  useEffect(() => {
    if (session.isConnected) {
      hasConnectedRef.current = true;
    } else if (hasConnectedRef.current) {
      onDisconnect();
    }
  }, [session.isConnected, onDisconnect]);

  return (
    <SessionProvider session={session}>
      <div className="relative h-screen w-screen overflow-hidden bg-background">
        {/* Minimal floating header */}
        <div className="pointer-events-none absolute inset-x-0 top-6 z-50 flex flex-col items-center">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground text-sm font-bold shadow">
            V
          </div>
          <p className="mt-1 text-xs font-semibold text-foreground/70">{agentName}</p>
        </div>

        <AgentSessionView_01
          audioVisualizerType="aura"
          audioVisualizerColor="#1FD5F9"
          audioVisualizerColorShift={0.1}
          supportsChatInput={false}
          supportsVideoInput={false}
          supportsScreenShare={false}
          preConnectMessage="Listening… ask me anything"
          isPreConnectBufferEnabled={true}
        />
        <RoomAudioRenderer />
      </div>
    </SessionProvider>
  );
}

// ── Shell layout (pre-call states) ────────────────────────────

function DemoShell({
  agentName,
  expiresAt,
  children,
}: {
  agentName: string;
  expiresAt?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground text-2xl font-bold shadow-md">
            V
          </div>
          <h1 className="text-2xl font-bold">{agentName}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Powered by SphereVoice</p>
          {expiresAt && (
            <p className="mt-2 text-xs text-muted-foreground">
              Link expires {new Date(expiresAt).toLocaleDateString()}
            </p>
          )}
        </div>
        <div className="rounded-2xl border bg-card p-8 shadow-sm">
          {children}
        </div>
        <p className="mt-6 text-center text-xs text-muted-foreground">
          This is a demo link shared by your provider.
        </p>
      </div>
    </div>
  );
}

