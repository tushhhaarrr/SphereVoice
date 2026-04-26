"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    ArrowDown,
    ArrowRight,
    ArrowUp,
    Clock,
    Phone,
    PhoneOff,
    Activity,
    CheckCircle,
    Timer,
    Zap,
} from "lucide-react";
import type { MetricCardsResponse, TrendIndicator } from "../types";

interface MetricCardsProps {
    data: MetricCardsResponse | undefined;
    isLoading: boolean;
}

function formatDuration(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
}

function formatLatency(ms: number): string {
    return `${Math.round(ms)}ms`;
}

function TrendBadge({ trend }: { trend: TrendIndicator | undefined }) {
    if (!trend) return null;
    const { value, direction } = trend;
    const isPositive = direction === "up";
    const isNeutral = direction === "flat";

    return (
        <span
            className={`inline-flex items-center gap-0.5 text-xs font-medium ${isNeutral
                    ? "text-muted-foreground"
                    : isPositive
                        ? "text-emerald-600"
                        : "text-red-600"
                }`}
        >
            {isNeutral ? (
                <ArrowRight className="h-3 w-3" />
            ) : isPositive ? (
                <ArrowUp className="h-3 w-3" />
            ) : (
                <ArrowDown className="h-3 w-3" />
            )}
            {Math.abs(value).toFixed(1)}%
        </span>
    );
}

interface MetricCardItem {
    title: string;
    value: string;
    trend?: TrendIndicator;
    icon: React.ReactNode;
    description: string;
}

export function MetricCards({ data, isLoading }: MetricCardsProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                    <Card key={i}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <div className="h-4 w-24 animate-pulse rounded bg-muted" />
                            <div className="h-4 w-4 animate-pulse rounded bg-muted" />
                        </CardHeader>
                        <CardContent>
                            <div className="h-8 w-20 animate-pulse rounded bg-muted" />
                            <div className="mt-1 h-3 w-16 animate-pulse rounded bg-muted" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    if (!data) return null;

    const total = data.total_calls ?? 0;
    const completed = data.completed_calls ?? 0;
    const failed = data.failed_calls ?? 0;
    const successRate = data.success_rate ?? 0;
    const avgDuration = data.avg_duration_seconds ?? 0;
    const totalDuration = data.total_duration_seconds ?? 0;
    const latencyP50 = data.avg_latency_p50_ms ?? 0;
    const active = data.active_calls ?? 0;

    const cards: MetricCardItem[] = [
        {
            title: "Total Calls",
            value: total.toLocaleString(),
            trend: data.trend_calls,
            icon: <Phone className="h-4 w-4 text-muted-foreground" />,
            description: "vs previous period",
        },
        {
            title: "Completed",
            value: completed.toLocaleString(),
            icon: <CheckCircle className="h-4 w-4 text-emerald-500" />,
            description: `${total > 0 ? ((completed / total) * 100).toFixed(1) : 0}% of total`,
        },
        {
            title: "Failed",
            value: failed.toLocaleString(),
            icon: <PhoneOff className="h-4 w-4 text-red-500" />,
            description: `${total > 0 ? ((failed / total) * 100).toFixed(1) : 0}% of total`,
        },
        {
            title: "Success Rate",
            value: `${successRate.toFixed(1)}%`,
            trend: data.trend_success_rate,
            icon: <Activity className="h-4 w-4 text-muted-foreground" />,
            description: "vs previous period",
        },
        {
            title: "Avg Duration",
            value: formatDuration(avgDuration),
            trend: data.trend_duration,
            icon: <Clock className="h-4 w-4 text-muted-foreground" />,
            description: "vs previous period",
        },
        {
            title: "Total Duration",
            value: formatDuration(totalDuration),
            icon: <Timer className="h-4 w-4 text-muted-foreground" />,
            description: "total call time",
        },
        {
            title: "Latency P50",
            value: formatLatency(latencyP50),
            trend: data.trend_latency,
            icon: <Zap className="h-4 w-4 text-muted-foreground" />,
            description: "first audio byte",
        },
        {
            title: "Active Calls",
            value: active.toLocaleString(),
            icon: <Activity className="h-4 w-4 text-emerald-500" />,
            description: "currently live",
        },
    ];

    return (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {cards.map((card) => (
                <Card key={card.title}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
                        {card.icon}
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{card.value}</div>
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                            {card.trend && <TrendBadge trend={card.trend} />}
                            {card.description}
                        </p>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
