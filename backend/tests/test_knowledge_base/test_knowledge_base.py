"""Tests for the Knowledge Base module.

Covers:
- Text chunking (unit)
- KB CRUD via API
- Document upload + text creation
- Vector search endpoint
- Agent ↔ KB attachment
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Tenant, User
from app.modules.knowledge_base.models import KBDocument, KnowledgeBase
from tests.conftest import ADMIN_ID, TENANT_1_ID, TENANT_2_ID, auth_headers

# ── Unit: Chunking ──────────────────────────────────────────────


class TestChunking:
    """Test text chunking logic."""

    def test_chunk_text_basic(self) -> None:
        from app.modules.knowledge_base.service import chunk_text

        text = "Hello world " * 1000  # ~2000 tokens
        chunks = chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c) > 0

    def test_chunk_text_small_document(self) -> None:
        from app.modules.knowledge_base.service import chunk_text

        text = "Short document."
        chunks = chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_empty(self) -> None:
        from app.modules.knowledge_base.service import chunk_text

        chunks = chunk_text("", chunk_size=512, overlap=50)
        assert len(chunks) == 0

    def test_chunk_overlap(self) -> None:
        from app.modules.knowledge_base.service import chunk_text

        # Generate a long enough text
        text = " ".join([f"word{i}" for i in range(2000)])
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2
        # Overlap means consecutive chunks share some content
        if len(chunks) >= 2:
            # Last words of chunk 0 should appear in chunk 1
            last_words_0 = chunks[0].split()[-5:]
            assert any(w in chunks[1] for w in last_words_0)


# ── Unit: File type detection ───────────────────────────────────


class TestFileTypeDetection:
    """Test file type detection."""

    def test_pdf(self) -> None:
        from app.modules.knowledge_base.service import detect_file_type

        assert detect_file_type("document.pdf") == "pdf"
        assert detect_file_type("DOCUMENT.PDF") == "pdf"

    def test_docx(self) -> None:
        from app.modules.knowledge_base.service import detect_file_type

        assert detect_file_type("file.docx") == "docx"

    def test_txt(self) -> None:
        from app.modules.knowledge_base.service import detect_file_type

        assert detect_file_type("notes.txt") == "txt"

    def test_unsupported(self) -> None:
        from app.core.exceptions import ValidationError
        from app.modules.knowledge_base.service import detect_file_type

        with pytest.raises(ValidationError):
            detect_file_type("image.png")

    def test_no_extension(self) -> None:
        from app.core.exceptions import ValidationError
        from app.modules.knowledge_base.service import detect_file_type

        with pytest.raises(ValidationError):
            detect_file_type("noextension")


# ── Unit: Text extraction ───────────────────────────────────────


class TestTextExtraction:
    """Test text extraction from various file formats."""

    def test_extract_txt(self) -> None:
        from app.modules.knowledge_base.service import extract_text_from_txt

        content = b"Hello, this is plain text content."
        result = extract_text_from_txt(content)
        assert result == "Hello, this is plain text content."

    def test_extract_txt_utf8(self) -> None:
        from app.modules.knowledge_base.service import extract_text_from_txt

        content = "Héllo wörld — special chars".encode("utf-8")
        result = extract_text_from_txt(content)
        assert "Héllo" in result


# ── Integration: KB CRUD API ────────────────────────────────────


@pytest_asyncio.fixture
async def admin_user_for_kb(db_session: AsyncSession) -> User:
    """Create or retrieve admin user for KB tests.

    Uses merge() to handle cases where the user already exists
    from a previous test that committed via the API.
    """
    user = User(
        id=ADMIN_ID,
        email="admin@Sphere.com",
        name="Admin User",
        role="admin",
        tenant_id=None,
        password_hash="$2b$12$test",
        is_active=True,
    )
    user = await db_session.merge(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def tenant_for_kb(db_session: AsyncSession) -> Tenant:
    """Create or retrieve test tenant for KB tests."""
    tenant = Tenant(id=TENANT_1_ID, name="Test Corp", slug="test-corp")
    tenant = await db_session.merge(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def other_tenant_for_kb(db_session: AsyncSession) -> Tenant:
    """Create or retrieve a second tenant for workspace filtering tests."""
    tenant = Tenant(id=TENANT_2_ID, name="Other Corp", slug="other-corp")
    tenant = await db_session.merge(tenant)
    await db_session.flush()
    return tenant


@pytest.mark.asyncio
class TestKnowledgeBaseCRUD:
    """Test KB CRUD operations via the API."""

    async def test_create_knowledge_base(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        payload = {
            "name": "Product FAQ",
            "description": "Frequently asked questions",
            "tenant_id": str(TENANT_1_ID),
            "sharing_scope": "tenant",
        }
        resp = await client.post("/api/v1/knowledge-bases", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Product FAQ"
        assert data["description"] == "Frequently asked questions"
        assert data["sharing_scope"] == "tenant"
        assert data["document_count"] == 0

    async def test_list_knowledge_bases(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        # Create a KB first
        await client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": "KB 1",
                "tenant_id": str(TENANT_1_ID),
            },
            headers=headers,
        )
        resp = await client.get("/api/v1/knowledge-bases", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_knowledge_bases_for_tenant_workspace(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
        other_tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)

        await client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": "Tenant KB",
                "tenant_id": str(TENANT_1_ID),
                "sharing_scope": "tenant",
            },
            headers=headers,
        )
        await client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": "Global KB",
                "sharing_scope": "global",
            },
            headers=headers,
        )
        await client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": "Other Tenant KB",
                "tenant_id": str(TENANT_2_ID),
                "sharing_scope": "tenant",
            },
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/knowledge-bases?tenant_id={TENANT_1_ID}",
            headers=headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        names = {item["name"] for item in data["items"]}
        assert "Tenant KB" in names
        assert "Global KB" in names
        assert "Other Tenant KB" not in names

    async def test_get_knowledge_base(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Get Test KB", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]
        resp = await client.get(
            f"/api/v1/knowledge-bases/{kb_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test KB"

    async def test_update_knowledge_base(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Old Name", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/knowledge-bases/{kb_id}",
            json={"name": "New Name", "description": "Updated desc"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["description"] == "Updated desc"

    async def test_delete_knowledge_base(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Delete Me", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]
        resp = await client.delete(
            f"/api/v1/knowledge-bases/{kb_id}", headers=headers
        )
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = await client.get(
            f"/api/v1/knowledge-bases/{kb_id}", headers=headers
        )
        assert resp2.status_code == 404

    async def test_get_nonexistent_kb_returns_404(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/knowledge-bases/{fake_id}", headers=headers
        )
        assert resp.status_code == 404


# ── Integration: Documents ──────────────────────────────────────


@pytest.mark.asyncio
class TestDocumentOperations:
    """Test document upload and management."""

    async def test_add_text_document(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        # Create KB
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Doc Test KB", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]

        # Add text document (mock Celery task)
        with patch(
            "app.workers.embeddings.generate_embeddings.delay"
        ) as mock_delay:
            resp = await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents/text",
                json={
                    "name": "FAQ Content",
                    "content": "What is SphereVoice? SphereVoice is a voice AI platform.",
                },
                headers=headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "FAQ Content"
            assert data["type"] == "text"
            assert data["status"] == "processing"
            mock_delay.assert_called_once()

    async def test_list_documents(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "List Doc KB", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]

        with patch("app.workers.embeddings.generate_embeddings.delay"):
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents/text",
                json={"name": "Doc 1", "content": "Content 1"},
                headers=headers,
            )
            await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents/text",
                json={"name": "Doc 2", "content": "Content 2"},
                headers=headers,
            )

        resp = await client.get(
            f"/api/v1/knowledge-bases/{kb_id}/documents", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_delete_document(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Del Doc KB", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]

        with patch("app.workers.embeddings.generate_embeddings.delay"):
            doc_resp = await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents/text",
                json={"name": "To Delete", "content": "Delete me"},
                headers=headers,
            )
        doc_id = doc_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}",
            headers=headers,
        )
        assert resp.status_code == 204

    async def test_upload_file_document(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Upload KB", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]

        # Upload a .txt file (mock blob upload + Celery)
        with (
            patch(
                "app.modules.knowledge_base.service.upload_to_blob",
                new_callable=AsyncMock,
                return_value="https://blob.example.com/test.txt",
            ),
            patch("app.workers.embeddings.generate_embeddings.delay"),
        ):
            resp = await client.post(
                f"/api/v1/knowledge-bases/{kb_id}/documents",
                files={"file": ("test.txt", b"File content here", "text/plain")},
                headers=headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "test.txt"
            assert data["type"] == "txt"


# ── Integration: Search ─────────────────────────────────────────


@pytest.mark.asyncio
class TestSearch:
    """Test vector search endpoint."""

    async def test_search_empty_kb(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
        tenant_for_kb: Tenant,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        create_resp = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Search KB", "tenant_id": str(TENANT_1_ID)},
            headers=headers,
        )
        kb_id = create_resp.json()["id"]

        # Mock the embedding call (no actual OpenAI)
        with patch(
            "app.modules.knowledge_base.retriever.generate_embeddings_batch",
            new_callable=AsyncMock,
            return_value=[[0.1] * 1536],
        ):
            resp = await client.get(
                f"/api/v1/knowledge-bases/{kb_id}/search",
                params={"q": "test query"},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["results"] == []
            assert data["query"] == "test query"

    async def test_search_nonexistent_kb(
        self,
        client: AsyncClient,
        admin_user_for_kb: User,
    ) -> None:
        headers = auth_headers(admin_user_for_kb)
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/knowledge-bases/{fake_id}/search",
            params={"q": "test"},
            headers=headers,
        )
        assert resp.status_code == 404
