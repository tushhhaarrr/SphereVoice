/**
 * Auth.js v5 configuration.
 *
 * Handles frontend session management via CredentialsProvider.
 * FastAPI backend issues JWT tokens for API calls.
 */

import NextAuth, { type DefaultSession } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998";
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
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
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
                    const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            email: credentials.email,
                            password: credentials.password,
                        }),
                    });

                    if (!res.ok) {
                        return null;
                    }

                    const data = await res.json();

                    return {
                        id: data.user.id,
                        email: data.user.email,
                        name: data.user.name || data.user.email,
                        role: data.user.role,
                        tenantId: data.user.tenant_id,
                        accessToken: data.access_token,
                        refreshToken: data.refresh_token,
                    };
                } catch {
                    return null;
                }
            },
        }),
    ],
    callbacks: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        authorized({ auth }: any) {
            // If token refresh permanently failed, force re-login so the user
            // doesn't end up on a protected page with an expired access token.
            if (auth?.error === "RefreshAccessTokenError") return false;
            return !!auth;
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        async jwt({ token, user }: any) {
            if (user) {
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
                return token;
            }

            const accessTokenExpires =
                typeof token.accessTokenExpires === "number"
                    ? token.accessTokenExpires
                    : readTokenExpiry(token.accessToken as string);

            if (
                accessTokenExpires &&
                Date.now() < accessTokenExpires - ACCESS_TOKEN_REFRESH_BUFFER_MS
            ) {
                return token;
            }

            return refreshAccessToken(token);
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        async session({ session, token }: any) {
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

