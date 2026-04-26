/**
 * Knowledge Base Module — Public API
 */

export type {
    KnowledgeBase,
    KnowledgeBaseListResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    KBDocument,
    DocumentListResponse,
    SearchResult,
    SearchResponse,
    AgentKBAttachment,
    SharingScope,
    DocumentStatus,
} from "./types";

export {
    useKnowledgeBases,
    useKnowledgeBase,
    useCreateKnowledgeBase,
    useUpdateKnowledgeBase,
    useDeleteKnowledgeBase,
    useKBDocuments,
    useUploadDocument,
    useAddTextDocument,
    useDeleteDocument,
    useSearchKB,
    useAgentKnowledgeBases,
    useAttachKBToAgent,
    useDetachKBFromAgent,
} from "./hooks/use-knowledge-base";

export { KnowledgeBaseList } from "./components/kb-list";
export { CreateKBDialog } from "./components/create-kb-dialog";
export { KBDetailPanel } from "./components/kb-detail-panel";
