/**
 * Next.js middleware — auth guard for protected routes.
 *
 * Redirects unauthenticated users to /login.
 * Allows public routes (login, api/auth) to pass through.
 */

export { auth as middleware } from "@/lib/auth";

export const config = {
    matcher: [
        /*
         * Match all routes EXCEPT:
         * - /login (auth page)
         * - /api/auth (Auth.js routes)
         * - /_next (Next.js internals)
         * - /favicon.ico, /public assets
         */
        "/((?!login|invite|api/auth|api/v1/share|share|_next/static|_next/image|favicon.ico).*)",
    ],
};
