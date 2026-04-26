"""Replace IVFFlat with HNSW index; add sharing-scope RLS for knowledge bases.

Revision ID: 002_hnsw_kb_sharing
Revises: 001_initial_schema
Create Date: 2025-01-15 00:00:00.000000

Changes:
  1. Drop IVFFlat index on kb_embeddings.embedding, create HNSW index.
     HNSW provides consistent <50ms query latency regardless of data distribution,
     no training data requirement, and superior recall at scale (100K+ chunks).
  2. Replace tenant_isolation_knowledge_bases RLS policy with a sharing-scope-aware
     policy that enforces: global → visible to all, tenant → visible to same
     tenant + admins, private → visible to creator + admins.
  3. Replace kb_documents and kb_embeddings RLS policies to inherit sharing scope
     from parent knowledge_bases.
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "002_hnsw_kb_sharing"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace IVFFlat with HNSW; add sharing-scope-aware RLS."""

    # ── 1. Replace IVFFlat index with HNSW ──────────────────────
    op.execute("DROP INDEX IF EXISTS idx_kb_embeddings_vector")
    op.execute(
        "CREATE INDEX idx_kb_embeddings_vector ON kb_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # ── 2. Sharing-scope-aware RLS for knowledge_bases ──────────
    # Drop existing simple tenant isolation policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation_knowledge_bases ON knowledge_bases")

    # New policy that respects sharing_scope:
    #   global   → visible to everyone (any authenticated user)
    #   tenant   → visible to same tenant + admins
    #   private  → visible to creator (created_by) + admins
    op.execute("""
        CREATE POLICY kb_sharing_scope_policy ON knowledge_bases
            FOR ALL
            USING (
                -- admins see everything
                current_setting('app.user_role', true) = 'admin'
                -- global KBs visible to all
                OR sharing_scope = 'global'
                -- tenant KBs visible to same tenant (+ NULL tenant = system KBs)
                OR (
                    sharing_scope = 'tenant'
                    AND (
                        tenant_id = current_setting('app.current_tenant_id', true)::UUID
                        OR tenant_id IS NULL
                    )
                )
                -- private KBs visible only to creator
                OR (
                    sharing_scope = 'private'
                    AND created_by = current_setting('app.current_user_id', true)::UUID
                )
            )
    """)

    # ── 3. Update kb_documents RLS to inherit sharing scope ─────
    op.execute("DROP POLICY IF EXISTS tenant_isolation_kb_documents ON kb_documents")
    op.execute("""
        CREATE POLICY kb_documents_scope_policy ON kb_documents
            FOR ALL
            USING (
                current_setting('app.user_role', true) = 'admin'
                OR kb_id IN (
                    SELECT id FROM knowledge_bases
                    WHERE
                        sharing_scope = 'global'
                        OR (
                            sharing_scope = 'tenant'
                            AND (
                                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                                OR tenant_id IS NULL
                            )
                        )
                        OR (
                            sharing_scope = 'private'
                            AND created_by = current_setting('app.current_user_id', true)::UUID
                        )
                )
            )
    """)

    # ── 4. Update kb_embeddings RLS to inherit sharing scope ────
    op.execute("DROP POLICY IF EXISTS tenant_isolation_kb_embeddings ON kb_embeddings")
    op.execute("""
        CREATE POLICY kb_embeddings_scope_policy ON kb_embeddings
            FOR ALL
            USING (
                current_setting('app.user_role', true) = 'admin'
                OR kb_id IN (
                    SELECT id FROM knowledge_bases
                    WHERE
                        sharing_scope = 'global'
                        OR (
                            sharing_scope = 'tenant'
                            AND (
                                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                                OR tenant_id IS NULL
                            )
                        )
                        OR (
                            sharing_scope = 'private'
                            AND created_by = current_setting('app.current_user_id', true)::UUID
                        )
                )
            )
    """)


def downgrade() -> None:
    """Revert to IVFFlat index and simple tenant-only RLS."""

    # Revert kb_embeddings RLS
    op.execute("DROP POLICY IF EXISTS kb_embeddings_scope_policy ON kb_embeddings")
    op.execute("""
        CREATE POLICY tenant_isolation_kb_embeddings ON kb_embeddings
            FOR ALL
            USING (
                kb_id IN (
                    SELECT id FROM knowledge_bases
                    WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
                       OR tenant_id IS NULL
                )
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # Revert kb_documents RLS
    op.execute("DROP POLICY IF EXISTS kb_documents_scope_policy ON kb_documents")
    op.execute("""
        CREATE POLICY tenant_isolation_kb_documents ON kb_documents
            FOR ALL
            USING (
                kb_id IN (
                    SELECT id FROM knowledge_bases
                    WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
                       OR tenant_id IS NULL
                )
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # Revert knowledge_bases RLS
    op.execute("DROP POLICY IF EXISTS kb_sharing_scope_policy ON knowledge_bases")
    op.execute("""
        CREATE POLICY tenant_isolation_knowledge_bases ON knowledge_bases
            FOR ALL
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::UUID
                OR current_setting('app.user_role', true) = 'admin'
                OR tenant_id IS NULL
            )
    """)

    # Revert HNSW to IVFFlat
    op.execute("DROP INDEX IF EXISTS idx_kb_embeddings_vector")
    op.execute(
        "CREATE INDEX idx_kb_embeddings_vector ON kb_embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
