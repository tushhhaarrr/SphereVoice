"use client";

/**
 * Role-based UI guard component.
 *
 * Wraps content that should only be visible to users with specific roles.
 * Hides content (or shows a fallback) for unauthorized roles.
 */

import { useSession } from "next-auth/react";

interface RoleGuardProps {
    /** Allowed roles — content is shown if the user has ANY of these roles */
    roles: string[];
    /** Content to show when the user has access */
    children: React.ReactNode;
    /** Optional fallback when the user does NOT have access */
    fallback?: React.ReactNode;
}

export function RoleGuard({ roles, children, fallback = null }: RoleGuardProps) {
    const { data: session, status } = useSession();

    if (status === "loading") {
        return null;
    }

    if (!session?.user?.role) {
        return <>{fallback}</>;
    }

    if (!roles.includes(session.user.role)) {
        return <>{fallback}</>;
    }

    return <>{children}</>;
}
