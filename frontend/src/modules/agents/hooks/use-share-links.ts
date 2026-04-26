/**
 * Share Links hook — CRUD for agent shareable demo links.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ExpiryPreset,
  ShareLink,
  ShareLinkCreateRequest,
  ShareLinkListResponse,
} from "../types/share-links";
import { fetchWithAuth } from "@/lib/api-client";

// ── Fetch ──────────────────────────────────────────────────

async function fetchShareLinks(agentId: string): Promise<ShareLink[]> {
  const res = await fetchWithAuth(`/api/v1/agents/${agentId}/share-links`);
  if (!res.ok) throw new Error(`Failed to load share links (${res.status})`);
  const data = (await res.json()) as ShareLinkListResponse;
  return data.links;
}

async function createShareLink(
  agentId: string,
  body: ShareLinkCreateRequest,
): Promise<ShareLink> {
  const res = await fetchWithAuth(`/api/v1/agents/${agentId}/share-links`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(err.detail ?? `Failed to create share link (${res.status})`);
  }
  return res.json() as Promise<ShareLink>;
}

async function revokeShareLink(agentId: string, linkId: string): Promise<void> {
  const res = await fetchWithAuth(`/api/v1/agents/${agentId}/share-links/${linkId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Failed to revoke share link (${res.status})`);
  }
}

// ── Hooks ──────────────────────────────────────────────────

export function useShareLinks(agentId: string) {
  return useQuery({
    queryKey: ["share-links", agentId],
    queryFn: () => fetchShareLinks(agentId),
    staleTime: 30_000,
  });
}

export function useCreateShareLink(agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ShareLinkCreateRequest) => createShareLink(agentId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["share-links", agentId] });
    },
  });
}

export function useRevokeShareLink(agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (linkId: string) => revokeShareLink(agentId, linkId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["share-links", agentId] });
    },
  });
}

// ── Helper ─────────────────────────────────────────────────

export function buildShareUrl(token: string): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin}/share/${token}`;
  }
  return `/share/${token}`;
}

export const EXPIRY_OPTIONS: { value: ExpiryPreset; label: string }[] = [
  { value: "15m", label: "15 minutes" },
  { value: "1h", label: "1 hour" },
  { value: "24h", label: "24 hours" },
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "never", label: "Never expires" },
];
