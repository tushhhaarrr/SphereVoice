/**
 * Auth.js v5 configuration.
 *
 * Handles frontend session management via CredentialsProvider.
 * FastAPI backend issues JWT tokens for API calls.
 */

import NextAuth, { type DefaultSession } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

// Strip trailing /api/v1 if present (backwards compat), then always append it
const _RAW_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998";
const API_BASE_URL = _RAW_BASE.replace(/\/api\/v1\/?$/, "") + "/api/v1";
const ACCESS_TOKEN_REFRESH_BUFFER_MS = 60 * 1000;

function readTokenExpiry(accessToken: string): number | null {
    try {
        const [, payload] = accessToken.split(".");
        if (!payload) {
            return null;
        }

        const decoded = JSON.parse(Buffer.from(payload, "base64url").toString("utf-8")) as {
            exp?: number;
        };

        return typeof decoded.exp === "number" ? decoded.exp * 1000 : null;
    } catch {
        return null;
    }
}

async function refreshAccessToken(token: Record<string, unknown>) {
    try {
        // FIXED: Removed duplicate /api/v1
        const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: token.refreshToken }),
        });

        if (!res.ok) {
            throw new Error("Failed to refresh access token");
        }

        const data = await res.json();
        return {
            ...token,
            accessToken: data.access_token,
            accessTokenExpires: readTokenExpiry(data.access_token),
            error: undefined,
        };
    } catch {
        return {
            ...token,
            error: "RefreshAccessTokenError",
        };
    }
}

declare module "next-auth" {
    interface Session {
        accessToken: string;
        refreshToken: string;
        error?: string;
        user: {
            id: string;
            email: string;
            name: string;
            role: string;
            tenantId: string | null;
        } & DefaultSession["user"];
    }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
    providers: [
        CredentialsProvider({
            name: "credentials",
            credentials: {
                email: { label: "Email", type: "email" },
                password: { label: "Password", type: "password" },
            },
            async authorize(credentials) {
                if (!credentials?.email || !credentials?.password) {
                    return null;
                }

                try {
                    // FIXED: Removed duplicate /api/v1
                    const res = await fetch(`${API_BASE_URL}/auth/login`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            email: credentials.email,
                            password: credentials.password,
                        }),
                    });

                    if (!res.ok) {
                        console.error("Backend rejected login. Status:", res.status);
                        return null;
                    }

                    const data = await res.json();
                    
                    // Safely extract the user object. 
                    // If backend doesn't return a nested 'user' object, fallback to defaults
                    const userObj = data.user || {};

                    return {
                        id: userObj.id || "admin-id",
                        email: userObj.email || credentials.email,
                        name: userObj.name || userObj.email || "Admin",
                        role: userObj.role || "admin",
                        tenantId: userObj.tenant_id || null,
                        accessToken: data.access_token,
                        refreshToken: data.refresh_token || "",
                    };
                } catch (error) {
                    console.error("Authorize fetch failed:", error);
                    return null;
                }
            },
        }),
    ],
    callbacks: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        authorized({ auth, request: { nextUrl } }: any) {
            console.log("[AUTH DEBUG] authorized callback triggered for URL:", nextUrl.pathname);
            console.log("[AUTH DEBUG] Current auth state:", JSON.stringify(auth));
            
            // If token refresh permanently failed, force re-login so the user
            // doesn't end up on a protected page with an expired access token.
            if (auth?.error === "RefreshAccessTokenError") {
                console.log("[AUTH DEBUG] Rejecting due to RefreshAccessTokenError");
                return false;
            }
            const isAuthorized = !!auth;
            console.log("[AUTH DEBUG] isAuthorized:", isAuthorized);
            return isAuthorized;
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        async jwt({ token, user, account }: any) {
            console.log("[AUTH DEBUG] jwt callback started");
            console.log("[AUTH DEBUG] is user object present?", !!user);
            
            if (user) {
                console.log("[AUTH DEBUG] Initial login, populating token from user object");
                token.accessToken = user.accessToken;
                token.refreshToken = user.refreshToken;
                token.accessTokenExpires = readTokenExpiry(user.accessToken);
                token.role = user.role;
                token.tenantId = user.tenantId;
                token.sub = user.id;
                token.email = user.email;
                token.name = user.name;
            }

            if (!token.accessToken || !token.refreshToken) {
                console.log("[AUTH DEBUG] Missing tokens, returning current token state");
                return token;
            }

            const accessTokenExpires =
                typeof token.accessTokenExpires === "number"
                    ? token.accessTokenExpires
                    : readTokenExpiry(token.accessToken as string);

            console.log("[AUTH DEBUG] Token expires at:", new Date(accessTokenExpires as number).toISOString());
            console.log("[AUTH DEBUG] Current time is: ", new Date().toISOString());

            if (
                accessTokenExpires &&
                Date.now() < accessTokenExpires - ACCESS_TOKEN_REFRESH_BUFFER_MS
            ) {
                console.log("[AUTH DEBUG] Token is still valid, no refresh needed.");
                return token;
            }

            console.log("[AUTH DEBUG] Token is expired or expiring soon, triggering refresh.");
            return refreshAccessToken(token);
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        async session({ session, token }: any) {
            console.log("[AUTH DEBUG] session callback mapping token to session object");
            session.accessToken = token.accessToken as string;
            session.refreshToken = token.refreshToken as string;
            session.error = token.error as string | undefined;
            session.user = {
                id: token.sub as string,
                email: token.email as string,
                name: token.name as string,
                role: token.role as string,
                tenantId: token.tenantId as string | null,
            };
            return session;
        },
    },
    pages: {
        signIn: "/login",
    },
    session: {
        strategy: "jwt",
    },
    trustHost: true,
});