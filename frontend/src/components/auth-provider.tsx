"use client";

/**
 * Session provider wrapper.
 *
 * Wraps the app with next-auth SessionProvider to enable
 * useSession() and other client-side auth hooks.
 */

import { SessionProvider } from "next-auth/react";

interface AuthProviderProps {
    children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
    return <SessionProvider>{children}</SessionProvider>;
}
