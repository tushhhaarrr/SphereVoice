"use client";

import { useRef, useState } from "react";
import {
  ExportMetricsButton,
  ExportTimeSeriesButton,
  ExtractionMetricsCards,
  FilterPanel,
  MetricCards,
  TimeSeriesChart,
  type FilterValues,
  useExtractionMetrics,
  useMetricCards,
  useTenants,
  useTimeSeries,
} from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

function getDefaultDates(): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

export default function AnalyticsPage() {
  const defaults = getDefaultDates();
  const chartRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const canPivotTenants = user?.role !== "client_user";

  const [filters, setFilters] = useState<FilterValues>({
    tenantId: "",
    metric: "call_count",
    granularity: "day",
    startDate: defaults.start,
    endDate: defaults.end,
    agentId: "",
  });

  const tenants = useTenants({ limit: 200, enabled: canPivotTenants });

  const metrics = useMetricCards({
    tenantId: filters.tenantId || undefined,
    startDate: filters.startDate || undefined,
    endDate: filters.endDate || undefined,
    agentId: filters.agentId || undefined,
  });

  const timeSeries = useTimeSeries({
    metric: filters.metric,
    granularity: filters.granularity,
    tenantId: filters.tenantId || undefined,
    startDate: filters.startDate || undefined,
    endDate: filters.endDate || undefined,
    agentId: filters.agentId || undefined,
  });

  const extractionMetrics = useExtractionMetrics({
    tenantId: filters.tenantId || undefined,
    startDate: filters.startDate || undefined,
    endDate: filters.endDate || undefined,
    agentId: filters.agentId || undefined,
  });

  const handleReset = () => {
    const d = getDefaultDates();
    setFilters({
      tenantId: "",
      metric: "call_count",
      granularity: "day",
      startDate: d.start,
      endDate: d.end,
      agentId: "",
    });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Call metrics and performance analytics
          </p>
        </div>
        <ExportMetricsButton metrics={metrics.data} />
      </div>

      <MetricCards data={metrics.data} isLoading={metrics.isLoading} />

      <ExtractionMetricsCards data={extractionMetrics.data} isLoading={extractionMetrics.isLoading} />

      <FilterPanel
        filters={filters}
        onChange={setFilters}
        onReset={handleReset}
        tenantOptions={tenants.data?.tenants ?? []}
        showTenantFilter={canPivotTenants}
      />

      <div className="space-y-2">
        <div className="flex justify-end">
          <ExportTimeSeriesButton
            timeSeries={timeSeries.data}
            chartRef={chartRef}
          />
        </div>
        <div ref={chartRef}>
          <TimeSeriesChart data={timeSeries.data} isLoading={timeSeries.isLoading} />
        </div>
      </div>
    </div>
  );
}
