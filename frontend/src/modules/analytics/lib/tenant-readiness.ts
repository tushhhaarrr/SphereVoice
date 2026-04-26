import type { TenantRecord } from "../types";

export type TenantReadinessKey =
    | "needs-activation"
    | "needs-team"
    | "needs-agent"
    | "needs-number"
    | "ready";

export interface TenantReadinessStage {
    key: TenantReadinessKey;
    label: string;
    detail: string;
    priority: number;
    badgeClassName: string;
}

export function getTenantReadinessStage(
    tenant: TenantRecord,
): TenantReadinessStage {
    if (tenant.status !== "active") {
        return {
            key: "needs-activation",
            label: "Needs Activation",
            detail: "Keep setup work in onboarding until the tenant is activated.",
            priority: 0,
            badgeClassName:
                "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
        };
    }

    if (tenant.summary.user_count === 0) {
        return {
            key: "needs-team",
            label: "Needs Team Setup",
            detail: "Invite the first client operator before handing off the workspace.",
            priority: 1,
            badgeClassName:
                "border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200",
        };
    }

    if (tenant.summary.agent_count === 0) {
        return {
            key: "needs-agent",
            label: "Needs Agent Setup",
            detail: "No voice agent is configured for this tenant yet.",
            priority: 2,
            badgeClassName:
                "border-violet-200 bg-violet-50 text-violet-900 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-200",
        };
    }

    if (tenant.summary.phone_number_count === 0) {
        return {
            key: "needs-number",
            label: "Needs Phone Number",
            detail: "Provision a number before marking this tenant ready for operations.",
            priority: 3,
            badgeClassName:
                "border-cyan-200 bg-cyan-50 text-cyan-900 dark:border-cyan-900 dark:bg-cyan-950 dark:text-cyan-200",
        };
    }

    return {
        key: "ready",
        label: "Ready for Ops",
        detail: "Core onboarding steps are in place. Operators can work from the tenant workspace.",
        priority: 4,
        badgeClassName:
            "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
    };
}