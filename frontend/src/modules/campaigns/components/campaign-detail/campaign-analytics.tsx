"use client";

import { Loader2, Download, TrendingUp, DollarSign, Phone, BarChart3 } from "lucide-react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCampaignAnalytics } from "../../hooks/use-campaigns";
import type { AgentVariantStats } from "../../types";

interface CampaignAnalyticsProps {
    campaignId: string;
    tenantId?: string;
}

const STATUS_COLORS: Record<string, string> = {
    completed: "#22c55e",
    failed: "#ef4444",
    pending: "#94a3b8",
    queued: "#3b82f6",
    calling: "#f59e0b",
    retry_scheduled: "#a855f7",
    skipped: "#6b7280",
    cancelled: "#71717a",
    no_answer: "#f97316",
    busy: "#ec4899",
    voicemail: "#8b5cf6",
};

const FUNNEL_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899"];

function formatDuration(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function formatCost(usd: number): string {
    if (usd < 0.01) return `$${usd.toFixed(4)}`;
    return `$${usd.toFixed(2)}`;
}

function handleExportPdf(campaignId: string) {
    // Build a printable summary and open print dialog as a PDF workaround
    window.print();
}

function VariantComparison({ variants }: { variants: AgentVariantStats[] }) {
    if (variants.length < 2) return null;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-base">A/B Test Results</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-2 gap-6">
                    {variants.map((v) => (
                        <div key={v.agent_id} className="space-y-3 rounded-lg border p-4">
                            <div className="flex items-center justify-between">
                                <span className="font-medium">{v.label}</span>
                                <Badge variant="outline" className="text-xs">
                                    {v.total_contacts} contacts
                                </Badge>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <div>
                                    <p className="text-muted-foreground">Connection Rate</p>
                                    <p className="text-lg font-semibold">{v.connection_rate}%</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Qualification Rate</p>
                                    <p className="text-lg font-semibold">{v.qualification_rate}%</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Avg Duration</p>
                                    <p className="text-lg font-semibold">{formatDuration(v.avg_duration_seconds)}</p>
                                </div>
                                <div>
                                    <p className="text-muted-foreground">Total Cost</p>
                                    <p className="text-lg font-semibold">{formatCost(v.total_cost)}</p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

export function CampaignAnalytics({ campaignId, tenantId }: CampaignAnalyticsProps) {
    const { data: analytics, isLoading, error } = useCampaignAnalytics(campaignId, tenantId);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-16 text-muted-foreground">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Loading analytics…
            </div>
        );
    }

    if (error || !analytics) {
        return (
            <div className="py-16 text-center text-muted-foreground">
                Failed to load analytics. Make sure the campaign has contacts.
            </div>
        );
    }

    const statusData = Object.entries(analytics.status_distribution).map(([status, count]) => ({
        name: status.replace(/_/g, " "),
        value: count,
        color: STATUS_COLORS[status] ?? "#94a3b8",
    }));

    const funnelData = analytics.conversion_funnel.map((stage, i) => ({
        ...stage,
        fill: FUNNEL_COLORS[i % FUNNEL_COLORS.length],
    }));

    return (
        <div className="space-y-6 print:space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between print:hidden">
                <h3 className="text-lg font-semibold">Campaign Analytics</h3>
                <Button variant="outline" size="sm" onClick={() => handleExportPdf(campaignId)}>
                    <Download className="mr-1 h-4 w-4" />
                    Export PDF
                </Button>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Phone className="h-4 w-4" />
                            Connection Rate
                        </div>
                        <p className="mt-1 text-2xl font-bold">{analytics.connection_rate}%</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <BarChart3 className="h-4 w-4" />
                            Avg Duration
                        </div>
                        <p className="mt-1 text-2xl font-bold">{formatDuration(analytics.avg_call_duration_seconds)}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <TrendingUp className="h-4 w-4" />
                            Extraction Rate
                        </div>
                        <p className="mt-1 text-2xl font-bold">{analytics.extraction_complete_rate}%</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <DollarSign className="h-4 w-4" />
                            Cost per Contact
                        </div>
                        <p className="mt-1 text-2xl font-bold">{formatCost(analytics.cost_per_contact)}</p>
                        <p className="text-xs text-muted-foreground">Total: {formatCost(analytics.total_cost)}</p>
                    </CardContent>
                </Card>
            </div>

            {/* CRM Writeback Rate */}
            <div className="grid grid-cols-2 gap-4">
                <Card>
                    <CardContent className="pt-4">
                        <p className="text-sm text-muted-foreground">CRM Writeback Success</p>
                        <p className="mt-1 text-2xl font-bold">{analytics.crm_writeback_success_rate}%</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4">
                        <p className="text-sm text-muted-foreground">Total Contacts</p>
                        <p className="mt-1 text-2xl font-bold">{analytics.total_contacts.toLocaleString()}</p>
                    </CardContent>
                </Card>
            </div>

            {/* Conversion Funnel */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Conversion Funnel</CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={funnelData} layout="vertical" margin={{ left: 100 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                            <XAxis type="number" />
                            <YAxis type="category" dataKey="stage" width={90} tick={{ fontSize: 12 }} />
                            <Tooltip
                                formatter={(value, _name, props) => [
                                    `${value} (${(props?.payload as Record<string, number>)?.percent ?? 0}%)`,
                                    "Count",
                                ]}
                            />
                            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                                {funnelData.map((entry, idx) => (
                                    <Cell key={idx} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Status Distribution Pie */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Status Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col items-center gap-4 md:flex-row">
                        <ResponsiveContainer width="100%" height={260}>
                            <PieChart>
                                <Pie
                                    data={statusData}
                                    dataKey="value"
                                    nameKey="name"
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={100}
                                    innerRadius={50}
                                    paddingAngle={2}
                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                >
                                    {statusData.map((entry, idx) => (
                                        <Cell key={idx} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                        <div className="flex flex-wrap gap-2">
                            {statusData.map((s) => (
                                <div key={s.name} className="flex items-center gap-1.5 text-xs">
                                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                                    {s.name}: {s.value}
                                </div>
                            ))}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* A/B Test Comparison */}
            {analytics.variant_stats && analytics.variant_stats.length > 0 && (
                <VariantComparison variants={analytics.variant_stats} />
            )}
        </div>
    );
}
