/**
 * API client — fetch wrapper with JWT Bearer token from Auth.js session.
 *
 * All API calls to the FastAPI backend go through this client.
 */

import { auth } from "@/lib/auth";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998").replace(/\/api\/v1\/?$/, "");

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async getHeaders(): Promise<HeadersInit> {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    // Inject JWT from Auth.js session (server-side)
    try {
      const session = await auth();
      if (session?.accessToken) {
        headers["Authorization"] = `Bearer ${session.accessToken}`;
      }
    } catch {
      // Not in a server context or no session — skip
    }

    return headers;
  }

  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (options?.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
    }

    const response = await fetch(url.toString(), {
      ...options,
      method: "GET",
      headers: await this.getHeaders(),
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }

    return response.json();
  }

  async post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      method: "POST",
      headers: await this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }

    return response.json();
  }

  async put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      method: "PUT",
      headers: await this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }

    return response.json();
  }

  async delete(path: string, options?: RequestOptions): Promise<void> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      method: "DELETE",
      headers: await this.getHeaders(),
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }
  }
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(`API Error: ${status}`);
    this.status = status;
    this.data = data;
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

// ── Client-side authenticated fetch ────────────────────────────────────────
//
// Used by TanStack Query hooks (client components) where server-side
// `auth()` is not available.  All 401 responses and expired-session
// states throw `AuthError`, which is caught by the global QueryCache
// error handler in QueryProvider (signs the user out → /login).

/**
 * Thrown when the API request is not authenticated.
 * QueryProvider catches this globally and signs the user out.
 */
export class AuthError extends Error {
  constructor(message = "Session expired. Please sign in again.") {
    super(message);
    this.name = "AuthError";
  }
}

/**
 * Fetches `path` (relative to the backend base URL) with the current
 * NextAuth session's Bearer token.
 *
 * Throws `AuthError` on:
 *  - `RefreshAccessTokenError` (both tokens permanently expired)
 *  - HTTP 401 from the backend
 *
 * All other non-2xx responses are returned as-is so hooks can surface
 * domain-specific error messages.
 */
export async function fetchWithAuth(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const { getSession } = await import("next-auth/react");
  const session = await getSession();

  // Both access + refresh tokens expired → force re-login.
  if (
    (session as Record<string, unknown> | null)?.error ===
    "RefreshAccessTokenError"
  ) {
    throw new AuthError();
  }

  const headers: HeadersInit = {
    // Skip Content-Type for FormData — browser sets it with multipart boundary.
    ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(init?.headers ?? {}),
  };

  if (session?.accessToken) {
    (headers as Record<string, string>)["Authorization"] =
      `Bearer ${session.accessToken}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (res.status === 401) {
    throw new AuthError();
  }

  return res;
}
