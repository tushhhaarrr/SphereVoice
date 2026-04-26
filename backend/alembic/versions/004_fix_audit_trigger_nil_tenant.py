"""Fix audit trigger handling for sentinel admin tenant context.

Revision ID: 004_fix_audit_trigger_nil_tenant
Revises: 003
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "004_fix_audit_trigger_nil_tenant"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger_func()
        RETURNS TRIGGER AS $$
        DECLARE
            _user_id UUID;
            _tenant_id UUID;
            _raw_tenant_id TEXT;
            _changes JSONB;
        BEGIN
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


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger_func()
        RETURNS TRIGGER AS $$
        DECLARE
            _user_id UUID;
            _tenant_id UUID;
            _changes JSONB;
        BEGIN
            BEGIN
                _user_id := current_setting('app.current_user_id', true)::UUID;
            EXCEPTION WHEN OTHERS THEN
                _user_id := NULL;
            END;
            BEGIN
                _tenant_id := current_setting('app.current_tenant_id', true)::UUID;
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