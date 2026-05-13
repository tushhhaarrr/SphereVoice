"use server";

/**
 * Server Action: Credentials Sign-In
 *
 * Auth.js v5 (beta) requires credentials login to go through a Server Action
 * rather than the client-side signIn("credentials") from next-auth/react.
 *
 * Root cause of the bug:
 * The client-side signIn("credentials", { redirect: false }) posts to
 * /api/auth/signin/credentials (the Auth.js form-page handler).
 * In Auth.js v5 beta, this route silently returns a redirect to /api/auth/signin
 * without setting a session cookie — so authorize() is never actually called
 * and the login always fails. This affects ALL users but is especially visible
 * for admin because there is no fallback/cached session.
 *
 * The fix: use the server-side signIn() from "@/lib/auth" inside a Server Action.
 * This correctly calls the callback route (/api/auth/callback/credentials) which
 * invokes authorize(), validates credentials, and sets the session cookie.
 */

import { signIn } from "@/lib/auth";

export async function credentialsSignIn(
    _prevState: { error: string | null },
    formData: FormData
): Promise<{ error: string | null }> {
    try {
        await signIn("credentials", {
            email: formData.get("email") as string,
            password: formData.get("password") as string,
            redirectTo: "/agents",
        });
        // signIn with redirectTo throws NEXT_REDIRECT internally —
        // if we somehow reach here without throwing, it's a success.
        return { error: null };
    } catch (err) {
        const errMsg = (err as Error)?.message ?? "";

        // Auth.js signals successful redirect via a thrown NEXT_REDIRECT —
        // we MUST re-throw it so Next.js performs the actual navigation.
        if (errMsg.includes("NEXT_REDIRECT") || errMsg.includes("NEXT_NOT_FOUND")) {
            throw err;
        }

        // CredentialsSignin is thrown when authorize() returns null (wrong password / user not found)
        // CallbackRouteError wraps it at the route level
        if (
            errMsg.toLowerCase().includes("credentialssignin") ||
            errMsg.toLowerCase().includes("callbackrouteerror") ||
            errMsg.toLowerCase().includes("invalid") ||
            errMsg.toLowerCase().includes("unauthorized")
        ) {
            return { error: "Invalid email or password" };
        }

        // Log unexpected errors in dev without exposing them to the user
        console.error("[credentialsSignIn] Unexpected error:", err);
        return { error: "Invalid email or password" };
    }
}
