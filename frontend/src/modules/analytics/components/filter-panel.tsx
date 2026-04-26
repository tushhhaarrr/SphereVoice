"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type { Granularity, TenantRecord, TimeSeriesMetric } from "../types";

export interface FilterValues {
    metric: TimeSeriesMetric;
    granularity: Granularity;
    startDate: string;
    endDate: string;
    agentId: string;
    tenantId: string;
}

interface FilterPanelProps {
    filters: FilterValues;
    onChange: (filters: FilterValues) => void;
    onReset: () => void;
    tenantOptions?: TenantRecord[];
    showTenantFilter?: boolean;
}

const METRIC_OPTIONS: { value: TimeSeriesMetric; label: string }[] = [
    { value: "call_count", label: "Call Count" },
    { value: "avg_duration", label: "Avg Duration" },
    { value: "avg_latency", label: "Avg Latency" },
    { value: "success_rate", label: "Success Rate" },
    { value: "total_duration", label: "Total Duration" },
];

const GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [
    { value: "day", label: "Daily" },
    { value: "week", label: "Weekly" },
    { value: "month", label: "Monthly" },
];

export function FilterPanel({
    filters,
    onChange,
    onReset,
    tenantOptions = [],
    showTenantFilter = false,
}: FilterPanelProps) {
    return (
        <div className="flex flex-wrap items-end gap-4 rounded-lg border bg-card p-4">
            {showTenantFilter && (
                <div className="space-y-1.5">
                    <Label htmlFor="tenant">Tenant</Label>
                    <Select
                        value={filters.tenantId || "all"}
                        onValueChange={(v) =>
                            onChange({ ...filters, tenantId: v === "all" ? "" : v })
                        }
                    >
                        <SelectTrigger id="tenant" className="w-[220px]">
                            <SelectValue placeholder="All tenants" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All tenants</SelectItem>
                            {tenantOptions.map((tenant) => (
                                <SelectItem key={tenant.id} value={tenant.id}>
                                    {tenant.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            )}

            <div className="space-y-1.5">
                <Label htmlFor="metric">Metric</Label>
                <Select
                    value={filters.metric}
                    onValueChange={(v) =>
                        onChange({ ...filters, metric: v as TimeSeriesMetric })
                    }
                >
                    <SelectTrigger id="metric" className="w-[160px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {METRIC_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <Label htmlFor="granularity">Granularity</Label>
                <Select
                    value={filters.granularity}
                    onValueChange={(v) =>
                        onChange({ ...filters, granularity: v as Granularity })
                    }
                >
                    <SelectTrigger id="granularity" className="w-[130px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {GRANULARITY_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <Label htmlFor="start-date">Start Date</Label>
                <Input
                    id="start-date"
                    type="date"
                    value={filters.startDate}
                    onChange={(e) => onChange({ ...filters, startDate: e.target.value })}
                    className="w-[160px]"
                />
            </div>

            <div className="space-y-1.5">
                <Label htmlFor="end-date">End Date</Label>
                <Input
                    id="end-date"
                    type="date"
                    value={filters.endDate}
                    onChange={(e) => onChange({ ...filters, endDate: e.target.value })}
                    className="w-[160px]"
                />
            </div>

            <Button variant="outline" size="sm" onClick={onReset}>
                Reset
            </Button>
        </div>
    );
}
