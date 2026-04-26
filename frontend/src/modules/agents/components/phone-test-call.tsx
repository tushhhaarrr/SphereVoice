"use client";

import { useState } from "react";
import { Phone, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api-client";

interface PhoneTestCallProps {
  agentId: string;
}

export function PhoneTestCall({ agentId }: PhoneTestCallProps) {
  const [toNumber, setToNumber] = useState("");
  const [isDialing, setIsDialing] = useState(false);
  const [callId, setCallId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDial() {
    if (!toNumber.trim()) return;

    setIsDialing(true);
    setCallId(null);
    setError(null);
    try {
      const data = await apiClient.post<{ call_id: string; status: string }>(
        "/api/v1/pipeline/sip/test-call",
        { agent_id: agentId, to_number: toNumber.trim() },
      );
      setCallId(data.call_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start call");
    } finally {
      setIsDialing(false);
    }
  }

  return (
    <div className="rounded-xl border bg-muted/20 p-4 space-y-3">
      <div>
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Phone className="h-4 w-4" />
          Phone Test Call
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Dial a real phone number via SIP to test this agent end-to-end.
        </p>
      </div>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Label htmlFor="to-number" className="text-xs text-muted-foreground">
            Phone number (E.164)
          </Label>
          <Input
            id="to-number"
            placeholder="+1234567890"
            value={toNumber}
            onChange={(e) => setToNumber(e.target.value)}
            disabled={isDialing}
            className="mt-1"
          />
        </div>
        <Button onClick={handleDial} disabled={isDialing || !toNumber.trim()} size="sm">
          {isDialing ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              Dialing...
            </>
          ) : (
            <>
              <Phone className="mr-1.5 h-3.5 w-3.5" />
              Call
            </>
          )}
        </Button>
      </div>

      {callId && (
        <p className="flex items-center gap-1.5 text-xs text-green-600">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Call initiated — ID: <span className="font-mono">{callId.slice(0, 8)}...</span>
        </p>
      )}
      {error && (
        <p className="flex items-center gap-1.5 text-xs text-destructive">
          <XCircle className="h-3.5 w-3.5" />
          {error}
        </p>
      )}
    </div>
  );
}
