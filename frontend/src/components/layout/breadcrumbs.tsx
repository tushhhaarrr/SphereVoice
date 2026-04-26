"use client";

/**
 * Breadcrumbs component for dashboard navigation.
 *
 * Auto-generates breadcrumb trail from the current pathname.
 * Converts kebab-case and path segments to Title Case labels.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";

import { cn } from "@/lib/utils";

/** Map route segments to display labels. */
const SEGMENT_LABELS: Record<string, string> = {
    agency: "Agency",
    agents: "Agents",
    calls: "Call History",
    live: "Live Calls",
    "phone-numbers": "Phone Numbers",
    "knowledge-base": "Knowledge Base",
    providers: "Providers",
    analytics: "Analytics",
    onboarding: "Onboarding Queue",
    settings: "Settings",
    workspace: "Workspace",
    overview: "Overview",
    users: "Users",
    activity: "Activity",
    tenants: "Tenants",
};

const UUID_SEGMENT_RE =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function segmentToLabel(segment: string): string {
    if (SEGMENT_LABELS[segment]) {
        return SEGMENT_LABELS[segment];
    }
    if (UUID_SEGMENT_RE.test(segment)) {
        return "Tenant";
    }
    return segment
        .split("-")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

interface BreadcrumbsProps {
    className?: string;
}

export function Breadcrumbs({ className }: BreadcrumbsProps) {
    const pathname = usePathname();
    const segments = pathname.split("/").filter(Boolean);

    if (segments.length === 0) {
        return null;
    }

    return (
        <nav
            aria-label="Breadcrumb"
            className={cn("flex items-center gap-1.5 text-sm text-muted-foreground", className)}
        >
            <Link
                href="/"
                className="flex items-center gap-1 transition-colors hover:text-foreground"
            >
                <Home className="h-3.5 w-3.5" />
                <span className="sr-only">Home</span>
            </Link>

            {segments.map((segment, index) => {
                const href = "/" + segments.slice(0, index + 1).join("/");
                const isLast = index === segments.length - 1;
                const label = segmentToLabel(segment);

                return (
                    <span key={href} className="flex items-center gap-1.5">
                        <ChevronRight className="h-3.5 w-3.5" />
                        {isLast ? (
                            <span className="font-medium text-foreground">{label}</span>
                        ) : (
                            <Link
                                href={href}
                                className="transition-colors hover:text-foreground"
                            >
                                {label}
                            </Link>
                        )}
                    </span>
                );
            })}
        </nav>
    );
}
