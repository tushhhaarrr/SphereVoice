"""Initial schema — all tables, RLS policies, audit trigger.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2025-01-01 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables, indexes, RLS policies, and audit trigger."""

    # ── Extensions ──────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"vector\"")

    # ── Tenants ─────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_tenants_slug", "tenants", ["slug"])
    op.create_index("idx_tenants_status", "tenants", ["status"])

    # ── Users ───────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])
    op.create_index("idx_users_role", "users", ["role"])

    # ── Provider Keys ───────────────────────────────────────────
    op.create_table(
        "provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("provider_category", sa.String(50), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test_status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_provider_keys_tenant", "provider_keys", ["tenant_id"])
    op.create_index("idx_provider_keys_category", "provider_keys", ["provider_category"])
    op.create_index("idx_provider_keys_default", "provider_keys", ["is_default"], postgresql_where=sa.text("is_default = true"))
    op.create_index("idx_provider_keys_tenant_name", "provider_keys", ["tenant_id", "provider_name"], unique=True, postgresql_where=sa.text("tenant_id IS NOT NULL"))

    # ── Knowledge Bases ─────────────────────────────────────────
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sharing_scope", sa.String(20), server_default=sa.text("'private'"), nullable=False),
        sa.Column("default_chunk_count", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("default_similarity_threshold", sa.Numeric(3, 2), server_default=sa.text("0.7"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kb_tenant", "knowledge_bases", ["tenant_id"])
    op.create_index("idx_kb_scope", "knowledge_bases", ["sharing_scope"])

    # ── Agents ──────────────────────────────────────────────────
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("stt_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("llm_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tts_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("telephony_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("language", sa.String(10), server_default=sa.text("'en-US'"), nullable=False),
        sa.Column("voice_id", sa.String(100), nullable=True),
        sa.Column("voice_speed", sa.Numeric(3, 2), server_default=sa.text("1.0"), nullable=False),
        sa.Column("voice_volume", sa.Numeric(3, 2), server_default=sa.text("1.0"), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("llm_temperature", sa.Numeric(3, 2), server_default=sa.text("0.7"), nullable=False),
        sa.Column("max_call_duration_seconds", sa.Integer(), server_default=sa.text("3600"), nullable=False),
        sa.Column("end_on_silence_seconds", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("voicemail_detection", sa.String(20), server_default=sa.text("'hang_up'"), nullable=False),
        sa.Column("extraction_fields", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("webhook_events", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stt_provider_id"], ["provider_keys.id"]),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["provider_keys.id"]),
        sa.ForeignKeyConstraint(["tts_provider_id"], ["provider_keys.id"]),
        sa.ForeignKeyConstraint(["telephony_provider_id"], ["provider_keys.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agents_tenant", "agents", ["tenant_id"])
    op.create_index("idx_agents_type", "agents", ["type"])
    op.create_index("idx_agents_status", "agents", ["status"])

    # ── Agent Versions ──────────────────────────────────────────
    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )
    op.create_index("idx_agent_versions_agent", "agent_versions", ["agent_id"])

    # ── Agent ↔ Knowledge Base (M2M) ───────────────────────────
    op.create_table(
        "agent_knowledge_bases",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("similarity_threshold", sa.Numeric(3, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "kb_id"),
    )
    op.create_index("idx_agent_kb_agent", "agent_knowledge_bases", ["agent_id"])
    op.create_index("idx_agent_kb_kb", "agent_knowledge_bases", ["kb_id"])

    # ── KB Documents ────────────────────────────────────────────
    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kb_docs_kb", "kb_documents", ["kb_id"])

    # ── KB Embeddings (pgvector) ────────────────────────────────
    op.create_table(
        "kb_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        # vector(1536) column — added via raw SQL since Alembic doesn't know the type natively
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["kb_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kb_embeddings_doc", "kb_embeddings", ["document_id"])
    op.create_index("idx_kb_embeddings_kb", "kb_embeddings", ["kb_id"])

    # Add vector column via raw SQL
    op.execute("ALTER TABLE kb_embeddings ADD COLUMN embedding vector(1536)")
    # IVFFlat index on the vector column for cosine similarity search
    # Note: IVFFlat requires data to train, so we use a small lists value
    op.execute(
        "CREATE INDEX idx_kb_embeddings_vector ON kb_embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ── Phone Numbers ───────────────────────────────────────────
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("country_code", sa.String(5), nullable=True),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("provider_sid", sa.Text(), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fallback_number", sa.String(20), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("capabilities", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("monthly_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number"),
    )
    op.create_index("idx_phone_numbers_tenant", "phone_numbers", ["tenant_id"])
    op.create_index("idx_phone_numbers_agent", "phone_numbers", ["agent_id"])
    op.create_index("idx_phone_numbers_status", "phone_numbers", ["status"])

    # ── Calls ───────────────────────────────────────────────────
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_number", sa.String(20), nullable=False),
        sa.Column("to_number", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("disconnection_reason", sa.String(100), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("recording_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript", postgresql.JSONB(), nullable=True),
        sa.Column("turn_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_latency_ms", sa.Integer(), nullable=True),
        sa.Column("extracted_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("extraction_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stt_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("llm_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("tts_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("telephony_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("total_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("dynamic_variables", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phone_number_id"], ["phone_numbers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_calls_tenant", "calls", ["tenant_id"])
    op.create_index("idx_calls_agent", "calls", ["agent_id"])
    op.create_index("idx_calls_status", "calls", ["status"])
    op.create_index("idx_calls_started_at", "calls", ["started_at"])
    op.create_index("idx_calls_direction", "calls", ["direction"])
    op.execute("CREATE INDEX idx_calls_extracted_data ON calls USING GIN (extracted_data)")

    # ── Call Events ─────────────────────────────────────────────
    op.create_table(
        "call_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_call_events_call", "call_events", ["call_id"])
    op.create_index("idx_call_events_type", "call_events", ["event_type"])
    op.create_index("idx_call_events_timestamp", "call_events", ["timestamp"])

    # ── Webhooks ────────────────────────────────────────────────
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("secret", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_webhooks_tenant", "webhooks", ["tenant_id"])
    op.create_index("idx_webhooks_agent", "webhooks", ["agent_id"])

    # ── Webhook Deliveries ──────────────────────────────────────
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("webhook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_webhook_deliveries_webhook", "webhook_deliveries", ["webhook_id"])
    op.create_index("idx_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("idx_webhook_deliveries_created_at", "webhook_deliveries", ["created_at"])

    # ── Audit Logs ──────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_logs_user", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_tenant", "audit_logs", ["tenant_id"])
    op.create_index("idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])

    # ── ROW-LEVEL SECURITY ──────────────────────────────────────
    # Create a PostgreSQL role for authenticated application users
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated_users') THEN
                CREATE ROLE authenticated_users;
            END IF;
        END
        $$;
    """)

    # Create the application role (non-superuser) that RLS policies apply to.
    # In production, the app connects as this role. In dev, we SET ROLE to it.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'SphereVoice_app') THEN
                CREATE ROLE SphereVoice_app NOLOGIN;
            END IF;
        END
        $$
    """)
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO SphereVoice_app")
    op.execute("GRANT USAGE ON SCHEMA public TO SphereVoice_app")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO SphereVoice_app")
    # Ensure future tables created by postgres also get grants for SphereVoice_app
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO SphereVoice_app")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO SphereVoice_app")

    # Enable RLS on all tenant-scoped tables
    rls_tables = [
        "agents", "calls", "phone_numbers", "webhooks",
        "webhook_deliveries", "provider_keys", "knowledge_bases",
        "kb_documents", "kb_embeddings", "agent_knowledge_bases",
        "agent_versions", "call_events", "audit_logs",
    ]
    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # RLS policies for tenant-scoped tables with direct tenant_id
    direct_tenant_tables = [
        "agents", "calls", "phone_numbers", "webhooks", "provider_keys",
        "knowledge_bases", "audit_logs",
    ]
    for table in direct_tenant_tables:
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                FOR ALL
                USING (
                    tenant_id = current_setting('app.current_tenant_id', true)::UUID
                    OR current_setting('app.user_role', true) = 'admin'
                    OR tenant_id IS NULL
                )
        """)

    # RLS for agent_versions — join through agents.tenant_id
    op.execute("""
        CREATE POLICY tenant_isolation_agent_versions ON agent_versions
            FOR ALL
            USING (
                agent_id IN (
                    SELECT id FROM agents
                    WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
                )
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # RLS for agent_knowledge_bases — join through agents.tenant_id
    op.execute("""
        CREATE POLICY tenant_isolation_agent_knowledge_bases ON agent_knowledge_bases
            FOR ALL
            USING (
                agent_id IN (
                    SELECT id FROM agents
                    WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
                )
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # RLS for kb_documents — join through knowledge_bases.tenant_id
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

    # RLS for kb_embeddings — join through knowledge_bases.tenant_id
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

    # RLS for call_events — join through calls.tenant_id
    op.execute("""
        CREATE POLICY tenant_isolation_call_events ON call_events
            FOR ALL
            USING (
                call_id IN (
                    SELECT id FROM calls
                    WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
                )
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # RLS for webhook_deliveries — join through webhooks.tenant_id
    op.execute("""
        CREATE POLICY tenant_isolation_webhook_deliveries ON webhook_deliveries
            FOR ALL
            USING (
                webhook_id IN (
                    SELECT id FROM webhooks
                    WHERE tenant_id = current_setting('app.current_tenant_id', true)::UUID
                )
                OR current_setting('app.user_role', true) = 'admin'
            )
    """)

    # ── AUDIT TRIGGER ───────────────────────────────────────────
    # Generic audit trigger function that logs INSERT/UPDATE/DELETE
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger_func()
        RETURNS TRIGGER AS $$
        DECLARE
            _user_id UUID;
            _tenant_id UUID;
            _raw_tenant_id TEXT;
            _changes JSONB;
        BEGIN
            -- Try to read app.current_user_id and app.current_tenant_id from session
            BEGIN
                _user_id := current_setting('app.current_user_id', true)::UUID;
            EXCEPTION WHEN OTHERS THEN
                _user_id := NULL;
            END;
            BEGIN
                _raw_tenant_id := NULLIF(current_setting('app.current_tenant_id', true), '');
                IF _raw_tenant_id = '00000000-0000-0000-0000-000000000000' THEN
                    _tenant_id := NULL;
                ELSE
                    _tenant_id := _raw_tenant_id::UUID;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                _tenant_id := NULL;
            END;

            IF TG_OP = 'INSERT' THEN
                _changes := jsonb_build_object('new', to_jsonb(NEW));
                INSERT INTO audit_logs (action, resource_type, resource_id, changes, user_id, tenant_id)
                VALUES ('create_' || TG_TABLE_NAME, TG_TABLE_NAME, NEW.id, _changes, _user_id, _tenant_id);
                RETURN NEW;
            ELSIF TG_OP = 'UPDATE' THEN
                _changes := jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW));
                INSERT INTO audit_logs (action, resource_type, resource_id, changes, user_id, tenant_id)
                VALUES ('update_' || TG_TABLE_NAME, TG_TABLE_NAME, NEW.id, _changes, _user_id, _tenant_id);
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                _changes := jsonb_build_object('old', to_jsonb(OLD));
                INSERT INTO audit_logs (action, resource_type, resource_id, changes, user_id, tenant_id)
                VALUES ('delete_' || TG_TABLE_NAME, TG_TABLE_NAME, OLD.id, _changes, _user_id, _tenant_id);
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Attach audit trigger to key tables
    audited_tables = [
        "agents", "provider_keys", "users", "calls",
        "phone_numbers", "webhooks", "knowledge_bases",
    ]
    for table in audited_tables:
        op.execute(f"""
            CREATE TRIGGER audit_{table}_trigger
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION audit_trigger_func()
        """)

    # ── updated_at auto-update trigger ──────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Attach to all tables that have updated_at
    updated_at_tables = [
        "tenants", "users", "provider_keys", "agents",
        "knowledge_bases", "calls", "webhooks",
    ]
    for table in updated_at_tables:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        """)


def downgrade() -> None:
    """Drop all tables and cleanup."""
    # Drop triggers
    audited_tables = [
        "agents", "provider_keys", "users", "calls",
        "phone_numbers", "webhooks", "knowledge_bases",
    ]
    for table in audited_tables:
        op.execute(f"DROP TRIGGER IF EXISTS audit_{table}_trigger ON {table}")

    updated_at_tables = [
        "tenants", "users", "provider_keys", "agents",
        "knowledge_bases", "calls", "webhooks",
    ]
    for table in updated_at_tables:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}")

    op.execute("DROP FUNCTION IF EXISTS audit_trigger_func()")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")

    # Drop tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("call_events")
    op.drop_table("calls")
    op.drop_table("phone_numbers")
    op.drop_table("kb_embeddings")
    op.drop_table("kb_documents")
    op.drop_table("agent_knowledge_bases")
    op.drop_table("agent_versions")
    op.drop_table("agents")
    op.drop_table("knowledge_bases")
    op.drop_table("provider_keys")
    op.drop_table("users")
    op.drop_table("tenants")

    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")

    # Drop app role (must revoke privileges first)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'SphereVoice_app') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM SphereVoice_app';
                EXECUTE 'REVOKE USAGE ON SCHEMA public FROM SphereVoice_app';
                EXECUTE 'DROP ROLE SphereVoice_app';
            END IF;
        END
        $$
    """)
