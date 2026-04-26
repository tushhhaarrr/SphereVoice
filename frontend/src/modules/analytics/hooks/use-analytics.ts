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
            const res = await fetchWithAuth(`/api/v1/analytics/metrics${qs}`);
            if (!res.ok) throw new Error("Failed to fetch metrics");
            return res.json();
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
            const res = await fetchWithAuth(`/api/v1/analytics/time-series${qs}`);
            if (!res.ok) throw new Error("Failed to fetch time series");
            return res.json();
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
            const res = await fetchWithAuth(`/api/v1/analytics/extraction-metrics${qs}`);
            if (!res.ok) throw new Error("Failed to fetch extraction metrics");
            return res.json();
        },
        refetchInterval: 30000,
    });
}
