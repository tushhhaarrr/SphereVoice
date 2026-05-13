"use client";

/**
 * Knowledge Base data-fetching hooks using TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
    KnowledgeBase,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
    KBDocument,
    DocumentListResponse,
    ChunkListResponse,
    SearchResponse,
    AgentKBAttachment,
} from "../types";
import { fetchWithAuth } from "@/lib/api-client";

// ── KB Queries ──────────────────────────────────────────────

export function useKnowledgeBases(params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    tenantId?: string;
    enabled?: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    refetchInterval?: number | false | ((query: any) => number | false | undefined);
}) {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.pageSize) search.set("page_size", String(params.pageSize));
    if (params?.search) search.set("search", params.search);
    if (params?.tenantId) search.set("tenant_id", params.tenantId);
    const qs = search.toString() ? `?${search.toString()}` : "";

    return useQuery<KnowledgeBaseListResponse>({
        queryKey: ["knowledge-bases", params],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/knowledge-bases${qs}`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return { items: [], total: 0, page: 1, page_size: 20 } as KnowledgeBaseListResponse;
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { items: [], total: 0, page: 1, page_size: 20 } as KnowledgeBaseListResponse;
            }
        },
        enabled: params?.enabled ?? true,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        refetchInterval: params?.refetchInterval as any,
    });
}

export function useKnowledgeBase(id: string) {
    return useQuery<KnowledgeBase>({
        queryKey: ["knowledge-bases", id],
        queryFn: async () => {
            const res = await fetchWithAuth(`/api/v1/knowledge-bases/${id}`);
            if (!res.ok) throw new Error("Failed to fetch knowledge base");
            return res.json();
        },
        enabled: !!id,
    });
}

// ── KB Mutations ────────────────────────────────────────────

export function useCreateKnowledgeBase() {
    const queryClient = useQueryClient();

    return useMutation<KnowledgeBase, Error, KnowledgeBaseCreateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth("/api/v1/knowledge-bases", {
                method: "POST",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to create knowledge base");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
        },
    });
}

export function useUpdateKnowledgeBase(id: string) {
    const queryClient = useQueryClient();

    return useMutation<KnowledgeBase, Error, KnowledgeBaseUpdateRequest>({
        mutationFn: async (data) => {
            const res = await fetchWithAuth(`/api/v1/knowledge-bases/${id}`, {
                method: "PUT",
                body: JSON.stringify(data),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(
                    err.error?.message || "Failed to update knowledge base"
                );
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases", id] });
        },
    });
}

export function useDeleteKnowledgeBase() {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (id) => {
            const res = await fetchWithAuth(`/api/v1/knowledge-bases/${id}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error("Failed to delete knowledge base");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
        },
    });
}

// ── Document Queries ────────────────────────────────────────

export function useKBDocuments(kbId: string) {
    return useQuery<DocumentListResponse>({
        queryKey: ["knowledge-bases", kbId, "documents"],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/knowledge-bases/${kbId}/documents`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return { items: [], total: 0 } as DocumentListResponse;
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return { items: [], total: 0 } as DocumentListResponse;
            }
        },
        enabled: !!kbId,
    });
}

// ── Document Mutations ──────────────────────────────────────

export function useUploadDocument(kbId: string) {
    const queryClient = useQueryClient();

    return useMutation<KBDocument, Error, File>({
        mutationFn: async (file) => {
            const formData = new FormData();
            formData.append("file", file);
            const res = await fetchWithAuth(
                `/api/v1/knowledge-bases/${kbId}/documents`,
                {
                    method: "POST",
                    body: formData,
                }
            );
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to upload document");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["knowledge-bases", kbId, "documents"],
            });
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases", kbId] });
        },
    });
}

export function useAddTextDocument(kbId: string) {
    const queryClient = useQueryClient();

    return useMutation<
        KBDocument,
        Error,
        { name: string; content: string }
    >({
        mutationFn: async (data) => {
            const res = await fetchWithAuth(
                `/api/v1/knowledge-bases/${kbId}/documents/text`,
                {
                    method: "POST",
                    body: JSON.stringify(data),
                }
            );
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || "Failed to add text document");
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["knowledge-bases", kbId, "documents"],
            });
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases", kbId] });
        },
    });
}

export function useDeleteDocument(kbId: string) {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (docId) => {
            const res = await fetchWithAuth(
                `/api/v1/knowledge-bases/${kbId}/documents/${docId}`,
                { method: "DELETE" }
            );
            if (!res.ok) throw new Error("Failed to delete document");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["knowledge-bases", kbId, "documents"],
            });
            queryClient.invalidateQueries({ queryKey: ["knowledge-bases", kbId] });
        },
    });
}

// ── Search ──────────────────────────────────────────────────

export function useDocumentChunks(kbId: string, docId: string | null) {
    return useQuery<ChunkListResponse>({
        queryKey: ["knowledge-bases", kbId, "documents", docId, "chunks"],
        queryFn: async () => {
            const res = await fetchWithAuth(
                `/api/v1/knowledge-bases/${kbId}/documents/${docId}/chunks`
            );
            if (!res.ok) throw new Error("Failed to fetch chunks");
            return res.json();
        },
        enabled: !!kbId && !!docId,
    });
}

export function useSearchKB(
    kbId: string,
    query: string,
    options?: { limit?: number; threshold?: number }
) {
    const params = new URLSearchParams();
    params.set("q", query);
    if (options?.limit) params.set("limit", String(options.limit));
    if (options?.threshold) params.set("threshold", String(options.threshold));

    return useQuery<SearchResponse>({
        queryKey: ["knowledge-bases", kbId, "search", query, options],
        queryFn: async () => {
            const res = await fetchWithAuth(
                `/api/v1/knowledge-bases/${kbId}/search?${params.toString()}`
            );
            if (!res.ok) throw new Error("Failed to search knowledge base");
            return res.json();
        },
        enabled: !!kbId && !!query && query.length > 0,
    });
}

// ── Agent ↔ KB Attachment ───────────────────────────────────

export function useAgentKnowledgeBases(agentId: string) {
    return useQuery<AgentKBAttachment[]>({
        queryKey: ["agents", agentId, "knowledge-bases"],
        queryFn: async () => {
            try {
                const res = await fetchWithAuth(`/api/v1/agents/${agentId}/knowledge-bases`);
                if (res.status === 401 || res.status === 403) throw new Error("Unauthorized");
                if (!res.ok) return [] as AgentKBAttachment[];
                return res.json();
            } catch (err) {
                if ((err as Error).message === "Unauthorized") throw err;
                return [] as AgentKBAttachment[];
            }
        },
        enabled: !!agentId,
    });
}

export function useAttachKBToAgent(agentId: string) {
    const queryClient = useQueryClient();

    return useMutation<
        AgentKBAttachment,
        Error,
        { kb_id: string; chunk_count?: number; similarity_threshold?: number }
    >({
        mutationFn: async (body) => {
            const res = await fetchWithAuth(
                `/api/v1/agents/${agentId}/knowledge-bases`,
                {
                    method: "POST",
                    body: JSON.stringify(body),
                }
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(
                    (err as Record<string, Record<string, string>>).error?.message ||
                        "Failed to attach knowledge base"
                );
            }
            return res.json();
        },
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["agents", agentId, "knowledge-bases"],
            });
        },
    });
}

export function useDetachKBFromAgent(agentId: string) {
    const queryClient = useQueryClient();

    return useMutation<void, Error, string>({
        mutationFn: async (kbId) => {
            const res = await fetchWithAuth(
                `/api/v1/agents/${agentId}/knowledge-bases/${kbId}`,
                { method: "DELETE" }
            );
            if (!res.ok) throw new Error("Failed to detach knowledge base");
        },
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["agents", agentId, "knowledge-bases"],
            });
        },
    });
}
