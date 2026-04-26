"use client";

import { useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Download } from "lucide-react";
import type { TimeSeriesResponse, MetricCardsResponse } from "../types";

/** Export time-series data as CSV */
function exportTimeSeriesCSV(data: TimeSeriesResponse): void {
    const header = "Date,Value\n";
    const rows = data.data
        .map((p) => `${p.date},${p.value}`)
        .join("\n");
    const csv = header + rows;
    downloadBlob(csv, `${data.metric}_${data.granularity}.csv`, "text/csv");
}

/** Export metric cards as CSV */
function exportMetricsCSV(data: MetricCardsResponse): void {
    const rows = [
        "Metric,Value",
        `Total Calls,${data.total_calls}`,
        `Completed Calls,${data.completed_calls}`,
        `Failed Calls,${data.failed_calls}`,
        `Success Rate,${data.success_rate}`,
        `Avg Duration (s),${data.avg_duration_seconds}`,
        `Total Duration (s),${data.total_duration_seconds}`,
        `Avg Latency P50 (ms),${data.avg_latency_p50_ms}`,
        `Avg Latency P99 (ms),${data.avg_latency_p99_ms}`,
        `Active Calls,${data.active_calls}`,
    ].join("\n");
    downloadBlob(rows, "metrics.csv", "text/csv");
}

/** Export a chart element as PNG via canvas */
function exportChartPNG(chartRef: React.RefObject<HTMLDivElement | null>): void {
    const el = chartRef.current;
    if (!el) return;

    const svg = el.querySelector("svg");
    if (!svg) return;

    const svgData = new XMLSerializer().serializeToString(svg);
    const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.width * 2;
        canvas.height = img.height * 2;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.scale(2, 2);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);

        canvas.toBlob((blob) => {
            if (blob) {
                downloadBlob(blob, "chart.png", "image/png");
            }
        }, "image/png");
    };
    img.src = url;
}

/** Export a chart element as SVG */
function exportChartSVG(chartRef: React.RefObject<HTMLDivElement | null>): void {
    const el = chartRef.current;
    if (!el) return;

    const svg = el.querySelector("svg");
    if (!svg) return;

    const svgData = new XMLSerializer().serializeToString(svg);
    downloadBlob(svgData, "chart.svg", "image/svg+xml");
}

function downloadBlob(
    content: string | Blob,
    filename: string,
    mimeType: string
): void {
    const blob =
        content instanceof Blob
            ? content
            : new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ── Exports ─────────────────────────────────────────────────

interface ExportMetricsButtonProps {
    metrics: MetricCardsResponse | undefined;
}

export function ExportMetricsButton({ metrics }: ExportMetricsButtonProps) {
    if (!metrics) return null;

    return (
        <Button
            variant="outline"
            size="sm"
            onClick={() => exportMetricsCSV(metrics)}
        >
            <Download className="mr-1.5 h-4 w-4" />
            Export Metrics CSV
        </Button>
    );
}

interface ExportTimeSeriesButtonProps {
    timeSeries: TimeSeriesResponse | undefined;
    chartRef: React.RefObject<HTMLDivElement | null>;
}

export function ExportTimeSeriesButton({
    timeSeries,
    chartRef,
}: ExportTimeSeriesButtonProps) {
    if (!timeSeries) return null;

    return (
        <div className="flex items-center gap-2">
            <Button
                variant="outline"
                size="sm"
                onClick={() => exportTimeSeriesCSV(timeSeries)}
            >
                <Download className="mr-1.5 h-4 w-4" />
                CSV
            </Button>
            <Button
                variant="outline"
                size="sm"
                onClick={() => exportChartPNG(chartRef)}
            >
                PNG
            </Button>
            <Button
                variant="outline"
                size="sm"
                onClick={() => exportChartSVG(chartRef)}
            >
                SVG
            </Button>
        </div>
    );
}
