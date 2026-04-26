"use client";

/**
 * TanStack Query provider.
 *
 * Wraps the app with QueryClientProvider for data fetching hooks.
 * Globally handles AuthError (401 / expired session) by signing the
 * user out and redirecting to /login.
 */

import { useState } from "react";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { signOut } from "next-auth/react";
import { AuthError } from "@/lib/api-client";

interface QueryProviderProps {
    children: React.ReactNode;
}

function handleAuthError(error: unknown) {
    if (error instanceof AuthError) {
        signOut({ callbackUrl: "/login" });
    }
}

export function QueryProvider({ children }: QueryProviderProps) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                queryCache: new QueryCache({ onError: handleAuthError }),
                mutationCache: new MutationCache({ onError: handleAuthError }),
                defaultOptions: {
                    queries: {
                        staleTime: 30 * 1000, // 30 seconds
                        retry: (failureCount, error) => {
                            // Never retry auth errors — user needs to re-login.
                            if (error instanceof AuthError) return false;
                            return failureCount < 1;
                        },
                        refetchOnWindowFocus: false,
                    },
                },
            })
    );

    return (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
}
