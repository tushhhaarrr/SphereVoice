"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    ArrowDown,
    ArrowRight,
    ArrowUp,
    CheckCircle,
    Frown,
    BarChart3,
} from "lucide-react";
import type { ExtractionMetricsResponse, TrendIndicator } from "../types";

interface ExtractionMetricsCardsProps {
    data: ExtractionMetricsResponse | undefined;
    isLoading: boolean;
}

function TrendBadge({ trend }: { trend: TrendIndicator | null | undefined }) {
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

function SentimentBar({ distribution }: { distribution: Record<string, number> }) {
    const total = Object.values(distribution).reduce((s, v) => s + v, 0);
    if (total === 0) return <span className="text-sm text-muted-foreground">No data</span>;

    const colors: Record<string, string> = {
        positive: "bg-emerald-500",
        neutral: "bg-slate-400",
        negative: "bg-red-500",
        mixed: "bg-amber-500",
    };

    return (
        <div className="space-y-1.5 w-full">
            <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
                {Object.entries(distribution).map(([key, count]) => {
                    const pct = (count / total) * 100;
                    if (pct === 0) return null;
                    return (
                        <div
                            key={key}
                            className={`${colors[key] ?? "bg-slate-300"}`}
                            style={{ width: `${pct}%` }}
                        />
                    );
                })}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                {Object.entries(distribution).map(([key, count]) => {
                    const pct = total > 0 ? ((count / total) * 100).toFixed(0) : "0";
                    return (
                        <span key={key} className="text-xs text-muted-foreground flex items-center gap-1">
                            <span className={`inline-block h-2 w-2 rounded-full ${colors[key] ?? "bg-slate-300"}`} />
                            {key} {pct}%
                        </span>
                    );
                })}
            </div>
        </div>
    );
}

export function ExtractionMetricsCards({ data, isLoading }: ExtractionMetricsCardsProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
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

    const successRate = data.extraction_success_rate ?? 0;
    const avgScore = data.avg_success_score ?? 0;
    const frustrationRate = data.frustration_rate ?? 0;
    const withExtraction = data.calls_with_extraction ?? 0;
    const totalCalls = data.total_calls_in_period ?? 0;

    return (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Extraction Success</CardTitle>
                    <CheckCircle className="h-4 w-4 text-emerald-500" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{successRate.toFixed(1)}%</div>
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                        <TrendBadge trend={data.trend_success_rate} />
                        {withExtraction}/{totalCalls} calls · avg score {avgScore.toFixed(1)}
                    </p>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Customer Sentiment</CardTitle>
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <SentimentBar distribution={data.sentiment_distribution ?? {}} />
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Frustration Rate</CardTitle>
                    <Frown className="h-4 w-4 text-red-500" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{frustrationRate.toFixed(1)}%</div>
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                        <TrendBadge trend={data.trend_frustration_rate} />
                        vs previous period
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
