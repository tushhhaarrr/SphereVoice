"use client";

/**
 * Live Dashboard — Real-time monitoring of active voice calls.
 *
 * Features:
 * - Active call cards with duration counter
 * - Click-to-expand call detail with live transcript
 * - Real-time latency display (red if >500ms)
 * - End Call button for manual termination
 * - Connection status indicator with reconnect
 */

import { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Clock,
  Copy,
  Gauge,
  MessageSquare,
  Phone,
  PhoneCall,
  PhoneOff,
  Radio,
  RefreshCw,
  Wifi,
  WifiOff,
  Zap,
} from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useLiveCalls } from "../hooks/use-live-calls";
import type { LiveCall, TranscriptEntry, WebSocketStatus } from "../types";

// ── Helpers ─────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

const WS_STATUS_CONFIG: Record<
  WebSocketStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  connecting: {
    label: "Connecting",
    color: "bg-yellow-100 text-yellow-700",
    icon: <Wifi className="h-3 w-3 animate-pulse" />,
  },
  connected: {
    label: "Connected",
    color: "bg-green-100 text-green-700",
    icon: <Wifi className="h-3 w-3" />,
  },
  disconnected: {
    label: "Disconnected",
    color: "bg-gray-100 text-gray-700",
    icon: <WifiOff className="h-3 w-3" />,
  },
  error: {
    label: "Error",
    color: "bg-red-100 text-red-700",
    icon: <WifiOff className="h-3 w-3" />,
  },
};

// ── Component ───────────────────────────────────────────────

export function LiveDashboard() {
  const { calls, metrics, wsStatus, selectedCall, selectCall, endCall, reconnect } =
    useLiveCalls();
  const statusConfig = WS_STATUS_CONFIG[wsStatus];

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Live Monitoring</h1>
          <p className="text-sm text-muted-foreground">
            Monitor active calls in real-time
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={statusConfig.color}>
            <span className="mr-1">{statusConfig.icon}</span>
            {statusConfig.label}
          </Badge>
          {wsStatus !== "connected" && (
            <Button variant="outline" size="sm" onClick={reconnect}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
              Reconnect
            </Button>
          )}
        </div>
      </div>

      <Separator />

      {/* Metrics Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Active Calls"
          value={String(metrics.activeCalls)}
          icon={<PhoneCall className="h-4 w-4" />}
          color="text-green-600"
        />
        <MetricCard
          title="Total Today"
          value={String(metrics.totalCallsToday)}
          icon={<Phone className="h-4 w-4" />}
          color="text-blue-600"
        />
        <MetricCard
          title="Avg Duration"
          value={formatDuration(metrics.avgDuration)}
          icon={<Clock className="h-4 w-4" />}
          color="text-purple-600"
        />
        <MetricCard
          title="Avg Latency"
          value={`${metrics.avgLatencyMs}ms`}
          icon={<Zap className="h-4 w-4" />}
          color={metrics.avgLatencyMs < 300 ? "text-green-600" : "text-orange-600"}
        />
      </div>

      {/* Main content: either call detail or call grid */}
      {selectedCall ? (
        <CallDetailPanel
          call={selectedCall}
          onBack={() => selectCall(null)}
          onEndCall={endCall}
        />
      ) : (
        <CallGrid calls={calls} onSelectCall={selectCall} />
      )}
    </div>
  );
}

// ── Call Grid ───────────────────────────────────────────────

function CallGrid({
  calls,
  onSelectCall,
}: {
  calls: LiveCall[];
  onSelectCall: (id: string) => void;
}) {
  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold">
        Active Calls ({calls.length})
      </h2>
      {calls.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Radio className="mb-3 h-12 w-12 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">
              No active calls at the moment
            </p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              Calls will appear here when they start
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {calls.map((call) => (
            <LiveCallCard
              key={call.callId}
              call={call}
              onClick={() => onSelectCall(call.callId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Live Call Card ──────────────────────────────────────────

interface LiveCallCardProps {
  call: LiveCall;
  onClick: () => void;
}

function LiveCallCard({ call, onClick }: LiveCallCardProps) {
  const [durationSec, setDurationSec] = useState(call.duration);

  // Live duration counter
  useEffect(() => {
    const start = new Date(call.startedAt).getTime();
    const tick = () => {
      setDurationSec(Math.floor((Date.now() - start) / 1000));
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [call.startedAt]);

  const statusColors: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    ringing: "bg-yellow-100 text-yellow-700",
    on_hold: "bg-orange-100 text-orange-700",
    transferring: "bg-blue-100 text-blue-700",
    ending: "bg-red-100 text-red-700",
  };

  const latencyColor =
    call.metrics.latencyMs > 500
      ? "text-red-600"
      : call.metrics.latencyMs > 300
        ? "text-orange-500"
        : "text-green-600";

  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{call.agentName}</CardTitle>
          <Badge
            className={statusColors[call.status] ?? "bg-gray-100 text-gray-700"}
          >
            {call.status}
          </Badge>
        </div>
        <CardDescription className="text-xs">
          {call.direction === "inbound" ? "From" : "To"}: {call.callerNumber}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDuration(durationSec)}
          </span>
          {call.metrics.latencyMs > 0 && (
            <span className={`flex items-center gap-1 font-mono ${latencyColor}`}>
              <Gauge className="h-3 w-3" />
              {call.metrics.latencyMs}ms
            </span>
          )}
          <span className="flex items-center gap-1">
            <MessageSquare className="h-3 w-3" />
            {call.metrics.turnCount}
          </span>
        </div>
        {call.lastTranscript && (
          <p className="mt-2 truncate text-xs italic text-muted-foreground">
            &ldquo;{call.lastTranscript}&rdquo;
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Call Detail Panel ──────────────────────────────────────

function CallDetailPanel({
  call,
  onBack,
  onEndCall,
}: {
  call: LiveCall;
  onBack: () => void;
  onEndCall: (callId: string) => void;
}) {
  const [durationSec, setDurationSec] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Live duration counter
  useEffect(() => {
    const start = new Date(call.startedAt).getTime();
    const tick = () => setDurationSec(Math.floor((Date.now() - start) / 1000));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [call.startedAt]);

  // Auto-scroll transcript
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [call.transcript.length]);

  const latencyColor =
    call.metrics.latencyMs > 500
      ? "text-red-600 bg-red-50"
      : call.metrics.latencyMs > 300
        ? "text-orange-600 bg-orange-50"
        : "text-green-600 bg-green-50";

  return (
    <div className="flex flex-col gap-4">
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h2 className="text-lg font-semibold">{call.agentName}</h2>
          <p className="text-sm text-muted-foreground">
            {call.direction === "inbound" ? "From" : "To"}: {call.callerNumber}{" "}
            &rarr; {call.calledNumber}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void navigator.clipboard.writeText(call.callId);
            }}
          >
            <Copy className="mr-1 h-3.5 w-3.5" />
            ID
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <PhoneOff className="mr-1 h-3.5 w-3.5" />
                End Call
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>End this call?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will immediately terminate the call for both the AI agent
                  and the caller. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => onEndCall(call.callId)}>
                  End Call
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid gap-3 sm:grid-cols-4">
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Duration</span>
          </div>
          <p className="mt-1 text-xl font-bold tabular-nums">
            {formatDuration(durationSec)}
          </p>
        </Card>
        <Card className={`p-3 ${latencyColor}`}>
          <div className="flex items-center gap-2 text-sm">
            <Zap className="h-4 w-4" />
            <span>Latency</span>
            {call.metrics.latencyMs > 500 && (
              <AlertTriangle className="ml-auto h-4 w-4" />
            )}
          </div>
          <p className="mt-1 text-xl font-bold tabular-nums">
            {call.metrics.latencyMs > 0 ? `${call.metrics.latencyMs}ms` : "—"}
          </p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Turns</span>
          </div>
          <p className="mt-1 text-xl font-bold tabular-nums">
            {call.metrics.turnCount}
          </p>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Sentiment</span>
          </div>
          <p className="mt-1 text-xl font-bold">
            {call.sentiment ?? "—"}
          </p>
        </Card>
      </div>

      {/* Live Transcript */}
      <Card className="flex-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Live Transcript</CardTitle>
          <CardDescription>
            {call.transcript.length} message{call.transcript.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px] pr-4" ref={scrollRef}>
            {call.transcript.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <MessageSquare className="mb-2 h-8 w-8 opacity-30" />
                <p className="text-sm">Waiting for conversation to start...</p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {call.transcript.map((entry, idx) => (
                  <TranscriptBubble key={idx} entry={entry} />
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Transcript Bubble ──────────────────────────────────────

function TranscriptBubble({ entry }: { entry: TranscriptEntry }) {
  const isUser = entry.speaker === "user";
  return (
    <div className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${isUser
            ? "bg-muted text-foreground"
            : "bg-primary text-primary-foreground"
          }`}
      >
        <p>{entry.text}</p>
        <p
          className={`mt-1 text-[10px] ${isUser ? "text-muted-foreground" : "text-primary-foreground/60"
            }`}
        >
          {formatTime(entry.timestamp)}
          {entry.confidence != null && ` · ${Math.round(entry.confidence * 100)}%`}
        </p>
      </div>
    </div>
  );
}

// ── Metric Card ────────────────────────────────────────────

interface MetricCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}

function MetricCard({ title, value, icon, color }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div className={`rounded-md bg-muted p-2.5 ${color}`}>{icon}</div>
        <div>
          <p className="text-xs text-muted-foreground">{title}</p>
          <p className="text-xl font-bold tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}
