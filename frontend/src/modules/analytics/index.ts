/**
 * Analytics Module — Public API
 */

export type {
    MetricCardsResponse,
    TimeSeriesResponse,
    ExtractionMetricsResponse,
    TimeSeriesMetric,
    Granularity,
    AuditLogEntry,
    AuditLogListResponse,
    AgentTemplate,
    TemplateListResponse,
    UserProfile,
    UserListResponse,
    UserRole,
    TenantRecord,
    TenantListResponse,
    TenantCreateRequest,
    TenantUpdateRequest,
    TenantStatus,
} from "./types";

export { MetricCards } from "./components/metric-cards";
export { TimeSeriesChart } from "./components/time-series-chart";
export { FilterPanel } from "./components/filter-panel";
export { TemplateGallery } from "./components/template-gallery";
export { RetellTemplateImportDialog } from "./components/retell-template-import-dialog";
export { SaveAsTemplateDialog } from "./components/save-as-template-dialog";
export { UsersTable } from "./components/users-table";
export { AuditLogTable } from "./components/audit-log-table";
export { TenantsTable } from "./components/tenants-table";
export { ExportMetricsButton, ExportTimeSeriesButton } from "./components/export-buttons";
export { ExtractionMetricsCards } from "./components/extraction-metrics-cards";

export type { FilterValues } from "./components/filter-panel";
export { getTenantReadinessStage } from "./lib/tenant-readiness";
export type { TenantReadinessKey, TenantReadinessStage } from "./lib/tenant-readiness";

export { useMetricCards, useTimeSeries, useExtractionMetrics } from "./hooks/use-analytics";
export { useTemplates, useTemplate, useCreateTemplate, useTemplateToAgent } from "./hooks/use-templates";
export { useUsers, useInviteUser, useUpdateUser } from "./hooks/use-users";
export { useAuditLogs } from "./hooks/use-audit-logs";
export { useTenants, useTenant, useCreateTenant, useUpdateTenant, useSeedWebsiteKB } from "./hooks/use-tenants";
