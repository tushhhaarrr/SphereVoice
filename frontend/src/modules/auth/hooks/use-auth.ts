"use client";

/**
 * Auth hook — provides typed access to the current session/user.
 */

import { useSession } from "next-auth/react";

export interface AuthUser {
    id: string;
    email: string;
    name: string;
    role: string;
    tenantId: string | null;
}

export interface UseAuthReturn {
    user: AuthUser | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    isAdmin: boolean;
    canWrite: boolean;
}

export function useAuth(): UseAuthReturn {
    const { data: session, status } = useSession();

    const user: AuthUser | null = session?.user
        ? {
            id: session.user.id,
            email: session.user.email,
            name: session.user.name,
            role: session.user.role,
            tenantId: session.user.tenantId,
        }
        : null;

    return {
        user,
        isAuthenticated: status === "authenticated",
        isLoading: status === "loading",
        isAdmin: user?.role === "admin",
        canWrite: user?.role === "admin" || user?.role === "developer",
    };
}
