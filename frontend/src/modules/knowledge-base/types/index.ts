/**
 * Knowledge Base module types.
 */

export type SharingScope = "private" | "tenant" | "global";

export type DocumentStatus = "pending" | "processing" | "processed" | "failed";

export type KBStatus = "pending" | "processing" | "ready" | "failed";

export interface KnowledgeBase {
  id: string;
  tenant_id: string | null;
  name: string;
  description: string | null;
  sharing_scope: SharingScope;
  default_chunk_count: number;
  default_similarity_threshold: number;
  document_count: number;
  status: KBStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBase[];
  total: number;
  page: number;
  page_size: number;
}

export interface KnowledgeBaseCreateRequest {
  name: string;
  description?: string;
  tenant_id?: string;
  sharing_scope?: SharingScope;
  default_chunk_count?: number;
  default_similarity_threshold?: number;
}

export interface KnowledgeBaseUpdateRequest {
  name?: string;
  description?: string;
  sharing_scope?: SharingScope;
  default_chunk_count?: number;
  default_similarity_threshold?: number;
}

export interface KBDocument {
  id: string;
  kb_id: string;
  name: string;
  type: string;
  file_url: string | null;
  processed_at: string | null;
  chunk_count: number;
  status: DocumentStatus;
  created_at: string;
}

export interface DocumentListResponse {
  items: KBDocument[];
  total: number;
}

export interface SearchResult {
  chunk_text: string;
  similarity: number;
  document_name: string;
  document_id: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  kb_id: string;
}

export interface Chunk {
  id: string;
  chunk_index: number;
  chunk_text: string;
  created_at: string;
}

export interface ChunkListResponse {
  items: Chunk[];
  total: number;
  document_name: string;
}

export interface AgentKBAttachment {
  agent_id: string;
  kb_id: string;
  kb_name: string;
  chunk_count: number | null;
  similarity_threshold: number | null;
  created_at: string;
}
