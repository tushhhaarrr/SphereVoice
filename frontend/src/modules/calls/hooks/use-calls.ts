"use client";

/**
 * Call data-fetching hooks using TanStack Query.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Call, CallListResponse, CallListParams } from "../types";
import { fetchWithAuth } from "@/lib/api-client";

export function useCalls(params?: CallListParams) {
  const search = new URLSearchParams();
  if (params?.page) search.set("page", String(params.page));
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.status) search.set("status", params.status);
  if (params?.direction) search.set("direction", params.direction);
  if (params?.agent_id) search.set("agent_id", params.agent_id);
  if (params?.start_date) search.set("start_date", params.start_date);
  if (params?.end_date) search.set("end_date", params.end_date);
  if (params?.search) search.set("search", params.search);
  const qs = search.toString() ? `?${search.toString()}` : "";

  return useQuery<CallListResponse>({
    queryKey: ["calls", params],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/calls${qs}`);
      if (!res.ok) throw new Error("Failed to fetch calls");
      return res.json();
    },
  });
}

export function useCall(id: string) {
  return useQuery<Call>({
    queryKey: ["calls", id],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/calls/${id}`);
      if (!res.ok) throw new Error("Failed to fetch call");
      return res.json();
    },
    enabled: !!id,
    staleTime: 0,
    refetchOnMount: "always",
    // Auto-poll while extraction is still pending
    refetchInterval: (query) => {
      const call = query.state.data;
      if (
        call?.status === "completed" &&
        Object.keys(call.extracted_data ?? {}).length === 0 &&
        !call.extraction_completed_at
      ) {
        return 3000; // poll every 3s
      }
      return false;
    },
  });
}

export function useCallRecordingUrl(callId: string | null, hasRecording: boolean) {
  return useQuery<{ url: string | null }>({
    queryKey: ["calls", callId, "recording"],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/calls/${callId}/recording`);
      if (!res.ok) throw new Error("Failed to fetch recording URL");
      return res.json();
    },
    enabled: !!callId && hasRecording,
    staleTime: 50 * 60 * 1000, // SAS token valid ~1h, refresh at 50min
  });
}

export function useEndCall() {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; call_id: string }, Error, string>({
    mutationFn: async (callId: string) => {
      const res = await fetchWithAuth(`/api/v1/calls/${callId}/end`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to end call");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calls"] });
    },
  });
}

export function useReExtractCall() {
  const queryClient = useQueryClient();
  return useMutation<
    { status: string; extracted_data?: Record<string, unknown> },
    Error,
    string
  >({
    mutationFn: async (callId: string) => {
      const res = await fetchWithAuth(`/api/v1/calls/${callId}/extract`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to re-extract call data");
      return res.json();
    },
    onSuccess: (_data, callId) => {
      queryClient.invalidateQueries({ queryKey: ["calls", callId] });
      queryClient.invalidateQueries({ queryKey: ["calls"] });
    },
  });
}

/** Fetch current USD→INR exchange rate (cached for 30 min on client). */
export function useExchangeRate() {
  return useQuery<{ from: string; to: string; rate: string }>({
    queryKey: ["exchange-rate"],
    queryFn: async () => {
      const res = await fetchWithAuth("/api/v1/pricing/exchange-rate");
      if (!res.ok) throw new Error("Failed to fetch exchange rate");
      return res.json();
    },
    staleTime: 30 * 60 * 1000, // 30 minutes
  });
}

/** Tool execution audit entry. */
export interface ToolExecution {
  id: string;
  tool_name: string;
  tool_category: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  status: "success" | "failed" | "timeout" | "error";
  duration_ms: number;
  error: string | null;
  executed_at: string | null;
}

/** Fetch tool execution logs for a specific call. */
export function useCallToolExecutions(callId: string | null) {
  return useQuery<ToolExecution[]>({
    queryKey: ["calls", callId, "tool-executions"],
    queryFn: async () => {
      const res = await fetchWithAuth(`/api/v1/calls/${callId}/tool-executions`);
      if (!res.ok) throw new Error("Failed to fetch tool executions");
      return res.json();
    },
    enabled: !!callId,
    staleTime: 0,
  });
}
