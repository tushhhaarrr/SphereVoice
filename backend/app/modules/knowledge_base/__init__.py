"""Knowledge Base Module — Public API."""

from app.modules.knowledge_base.models import KBDocument, KBEmbedding, KnowledgeBase
from app.modules.knowledge_base.retriever import KnowledgeRetriever, search_kb
from app.modules.knowledge_base.service import CognitiveLibraryOrchestrator

__all__ = [
    "KnowledgeBase",
    "KBDocument",
    "KBEmbedding",
    "CognitiveLibraryOrchestrator",
    "KnowledgeRetriever",
    "search_kb",
]
