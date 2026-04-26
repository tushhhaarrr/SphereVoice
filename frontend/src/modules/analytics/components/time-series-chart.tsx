"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Area,
    AreaChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import type { TimeSeriesResponse } from "../types";

interface TimeSeriesChartProps {
    data: TimeSeriesResponse | undefined;
    isLoading: boolean;
    title?: string;
}

const METRIC_LABELS: Record<string, string> = {
    call_count: "Call Count",
    avg_duration: "Avg Duration (s)",
    avg_latency: "Avg Latency (ms)",
    success_rate: "Success Rate (%)",
    total_duration: "Total Duration (s)",
};

function formatValue(metric: string, value: number): string {
    switch (metric) {
        case "success_rate":
            return `${value.toFixed(1)}%`;
        case "avg_latency":
            return `${Math.round(value)}ms`;
        case "avg_duration":
        case "total_duration":
            return `${Math.round(value)}s`;
        default:
            return value.toLocaleString();
    }
}

export function TimeSeriesChart({
    data,
    isLoading,
    title,
}: TimeSeriesChartProps) {
    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">{title || "Time Series"}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="h-[300px] animate-pulse rounded bg-muted" />
                </CardContent>
            </Card>
        );
    }

    if (!data || data.data.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">{title || "Time Series"}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                        No data available for the selected period.
                    </div>
                </CardContent>
            </Card>
        );
    }

    const chartLabel =
        title || METRIC_LABELS[data.metric] || data.metric;

    const chartData = data.data.map((point) => ({
        date: new Date(point.date).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
        }),
        value: point.value,
    }));

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-base">{chartLabel}</CardTitle>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis
                            dataKey="date"
                            className="text-xs"
                            tick={{ fill: "hsl(var(--muted-foreground))" }}
                        />
                        <YAxis
                            className="text-xs"
                            tick={{ fill: "hsl(var(--muted-foreground))" }}
                            tickFormatter={(v: number) => formatValue(data.metric, v)}
                        />
                        <Tooltip
                            content={({ active, payload }) => {
                                if (!active || !payload?.length) return null;
                                const item = payload[0];
                                return (
                                    <div className="rounded-lg border bg-background p-3 shadow-md">
                                        <p className="text-sm font-medium">{item.payload.date}</p>
                                        <p className="text-sm text-muted-foreground">
                                            {chartLabel}: {formatValue(data.metric, item.value as number)}
                                        </p>
                                    </div>
                                );
                            }}
                        />
                        <Area
                            type="monotone"
                            dataKey="value"
                            stroke="hsl(var(--primary))"
                            strokeWidth={2}
                            fill="url(#colorValue)"
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}
