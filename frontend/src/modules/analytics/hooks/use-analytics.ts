"use client";

/**
 * Analytics data-fetching hooks using TanStack Query.
 */

import { useQuery } from "@tanstack/react-query";
import type {
    ExtractionMetricsResponse,
    Granularity,
    MetricCardsResponse,
    TimeSeriesMetric,
    TimeSeriesResponse,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── Metric Cards ────────────────────────────────────────────

export interface MetricCardsParams {
    tenantId?: string;
    agentId?: string;
    startDate?: string;
    endDate?: string;
}

export function useMetricCards(params?: MetricCardsParams) {
    const search = new URLSearchParams();
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    if (params?.agentId) search.set("agent_id", params.agentId);
    if (params?.startDate) search.set("start_date", params.startDate);
    if (params?.endDate) search.set("end_date", params.endDate);
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<MetricCardsResponse>({
        queryKey: ["analytics", "metrics", params],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/analytics/metrics${qs}`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return { total_calls: 0, completed_calls: 0, failed_calls: 0, avg_duration_seconds: 0, total_duration_seconds: 0, avg_latency_p50_ms: 0, avg_latency_p99_ms: 0, success_rate: 0, active_calls: 0, trend_calls: { value: 0, direction: "flat" }, trend_duration: { value: 0, direction: "flat" }, trend_latency: { value: 0, direction: "flat" }, trend_success_rate: { value: 0, direction: "flat" } } as MetricCardsResponse;
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { total_calls: 0, completed_calls: 0, failed_calls: 0, avg_duration_seconds: 0, total_duration_seconds: 0, avg_latency_p50_ms: 0, avg_latency_p99_ms: 0, success_rate: 0, active_calls: 0, trend_calls: { value: 0, direction: "flat" }, trend_duration: { value: 0, direction: "flat" }, trend_latency: { value: 0, direction: "flat" }, trend_success_rate: { value: 0, direction: "flat" } } as MetricCardsResponse;
            }
        },
        refetchInterval: 30000, // Refresh every 30 seconds
    });
}

// ── Time Series ─────────────────────────────────────────────

export interface TimeSeriesParams {
    metric?: TimeSeriesMetric;
    granularity?: Granularity;
    tenantId?: string;
    agentId?: string;
    startDate?: string;
    endDate?: string;
}

export function useTimeSeries(params?: TimeSeriesParams) {
    const search = new URLSearchParams();
    if (params?.metric) search.set("metric", params.metric);
    if (params?.granularity) search.set("granularity", params.granularity);
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    if (params?.agentId) search.set("agent_id", params.agentId);
    if (params?.startDate) search.set("start_date", params.startDate);
    if (params?.endDate) search.set("end_date", params.endDate);
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<TimeSeriesResponse>({
        queryKey: ["analytics", "time-series", params],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/analytics/time-series${qs}`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return { data: [], metric: params?.metric ?? "calls", granularity: params?.granularity ?? "day" } as TimeSeriesResponse;
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { data: [], metric: params?.metric ?? "calls", granularity: params?.granularity ?? "day" } as TimeSeriesResponse;
            }
        },
    });
}

// ── Extraction Metrics ──────────────────────────────────────

export interface ExtractionMetricsParams {
    tenantId?: string;
    agentId?: string;
    startDate?: string;
    endDate?: string;
}

export function useExtractionMetrics(params?: ExtractionMetricsParams) {
    const search = new URLSearchParams();
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    if (params?.agentId) search.set("agent_id", params.agentId);
    if (params?.startDate) search.set("start_date", params.startDate);
    if (params?.endDate) search.set("end_date", params.endDate);
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<ExtractionMetricsResponse>({
        queryKey: ["analytics", "extraction-metrics", params],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/analytics/extraction-metrics${qs}`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return { extraction_success_rate: 0, avg_success_score: 0, sentiment_distribution: {}, frustration_rate: 0, calls_with_extraction: 0, total_calls_in_period: 0, trend_success_rate: null, trend_frustration_rate: null } as ExtractionMetricsResponse;
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { extraction_success_rate: 0, avg_success_score: 0, sentiment_distribution: {}, frustration_rate: 0, calls_with_extraction: 0, total_calls_in_period: 0, trend_success_rate: null, trend_frustration_rate: null } as ExtractionMetricsResponse;
            }
        },
        refetchInterval: 30000,
    });
}
