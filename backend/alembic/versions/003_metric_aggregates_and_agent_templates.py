"""Add metric_aggregates and agent_templates tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002_hnsw_kb_sharing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── metric_aggregates table ──────────────────────────────
    op.create_table(
        "metric_aggregates",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("granularity", sa.String(10), nullable=False),
        sa.Column("total_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_duration_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_duration_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("p50_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("p95_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("p99_latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("success_rate", sa.Numeric(5, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("transfer_rate", sa.Numeric(5, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("voicemail_rate", sa.Numeric(5, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("peak_concurrency", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "agent_id", "period_date", "granularity", name="uq_metric_aggregates_period"),
    )
    op.create_index("idx_metric_aggregates_tenant", "metric_aggregates", ["tenant_id"])
    op.create_index("idx_metric_aggregates_agent", "metric_aggregates", ["agent_id"])
    op.create_index("idx_metric_aggregates_period", "metric_aggregates", ["period_date", "granularity"])

    # ── agent_templates table ────────────────────────────────
    op.create_table(
        "agent_templates",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("tags", ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("scope", sa.String(20), server_default=sa.text("'private'"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("config", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("voice_id", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), server_default=sa.text("'en-US'"), nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("llm_temperature", sa.Numeric(3, 2), server_default=sa.text("0.7"), nullable=False),
        sa.Column("extraction_fields", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("kb_suggestions", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_templates_tenant", "agent_templates", ["tenant_id"])
    op.create_index("idx_agent_templates_category", "agent_templates", ["category"])
    op.create_index("idx_agent_templates_builtin", "agent_templates", ["is_builtin"])

    # ── GRANT permissions to SphereVoice_app role ──────────────────────
    op.execute("GRANT ALL ON agent_templates TO SphereVoice_app")
    op.execute("GRANT ALL ON metric_aggregates TO SphereVoice_app")

    # ── Enable RLS on new tables ─────────────────────────────
    for table in ["agent_templates", "metric_aggregates"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                FOR ALL
                USING (
                    tenant_id = current_setting('app.current_tenant_id', true)::UUID
                    OR current_setting('app.user_role', true) = 'admin'
                    OR tenant_id IS NULL
                )
        """)

    # ── Seed 8 built-in templates ────────────────────────────
    op.execute("""
        INSERT INTO agent_templates (name, description, category, tags, is_builtin, scope, agent_type, config, extraction_fields)
        VALUES
        (
            'Patient Screening',
            'Healthcare voice agent for initial patient screening. Collects symptoms, urgency level, and routes to appropriate department.',
            'Healthcare',
            ARRAY['healthcare', 'screening', 'medical'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are a medical office assistant conducting initial patient screening. Greet the caller warmly, ask about their symptoms, urgency level (routine, urgent, emergency), current medications, and preferred appointment time. Be empathetic and professional. If the patient describes emergency symptoms (chest pain, difficulty breathing, severe bleeding), immediately advise them to call 911 or go to the nearest emergency room.", "functions": [{"name": "transfer_to_nurse", "description": "Transfer to a nurse for clinical questions"}, {"name": "book_appointment", "description": "Schedule a new appointment"}]}'::jsonb,
            '[{"name": "symptoms", "type": "text"}, {"name": "urgency", "type": "enum", "values": ["routine", "urgent", "emergency"]}, {"name": "preferred_date", "type": "date"}]'::jsonb
        ),
        (
            'Real Estate Lead Qualification',
            'Qualifies real estate leads by collecting budget, location preferences, timeline, and financing status.',
            'Real Estate',
            ARRAY['real-estate', 'lead-qualification', 'sales'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are a friendly real estate assistant qualifying potential buyers. Ask about their desired location/neighborhood, budget range, property type (house, condo, townhouse), number of bedrooms/bathrooms, timeline to purchase, and whether they have pre-approval for financing. Be enthusiastic but not pushy. If they seem ready, offer to schedule a showing with an agent.", "functions": [{"name": "schedule_showing", "description": "Schedule a property showing"}, {"name": "transfer_to_agent", "description": "Transfer to a real estate agent"}]}'::jsonb,
            '[{"name": "budget_range", "type": "text"}, {"name": "location", "type": "text"}, {"name": "property_type", "type": "text"}, {"name": "timeline", "type": "text"}, {"name": "pre_approved", "type": "boolean"}]'::jsonb
        ),
        (
            'Medical Center Receptionist',
            'Front desk receptionist for medical centers. Handles appointments, directions, hours, and general inquiries.',
            'Healthcare',
            ARRAY['healthcare', 'receptionist', 'appointments'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are the front desk receptionist at a medical center. Help callers with appointment scheduling, office hours, directions, insurance questions, and general inquiries. Be warm, professional, and efficient. For medical advice, always redirect to a nurse or doctor. Verify patient identity before discussing any medical records.", "functions": [{"name": "book_appointment", "description": "Schedule an appointment"}, {"name": "cancel_appointment", "description": "Cancel an existing appointment"}, {"name": "transfer_to_billing", "description": "Transfer to billing department"}]}'::jsonb,
            '[{"name": "reason_for_call", "type": "text"}, {"name": "appointment_scheduled", "type": "boolean"}, {"name": "insurance_verified", "type": "boolean"}]'::jsonb
        ),
        (
            'Real Estate Appointment Setter',
            'Sets property viewing appointments. Collects preferences and schedules showings with available agents.',
            'Real Estate',
            ARRAY['real-estate', 'appointments', 'scheduling'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are a real estate appointment coordinator. Your goal is to schedule property viewings for interested buyers. Confirm which property they are interested in, collect their preferred viewing dates and times, and verify their contact information. Check agent availability and confirm the appointment. Be professional, accommodating with scheduling, and provide any basic property details asked.", "functions": [{"name": "check_availability", "description": "Check agent availability for a given date/time"}, {"name": "book_showing", "description": "Confirm and book a property showing"}, {"name": "send_confirmation_sms", "description": "Send appointment confirmation via SMS"}]}'::jsonb,
            '[{"name": "property_address", "type": "text"}, {"name": "viewing_date", "type": "date"}, {"name": "viewing_time", "type": "text"}, {"name": "appointment_confirmed", "type": "boolean"}]'::jsonb
        ),
        (
            'Delivery Customer Support',
            'Handles delivery status inquiries, rescheduling, complaints, and refund requests.',
            'Customer Support',
            ARRAY['delivery', 'customer-support', 'logistics'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are a customer support agent for a delivery service. Help customers with order tracking, delivery status updates, rescheduling deliveries, filing complaints about damaged packages, and processing refund requests. Always start by asking for the order number. Be patient, empathetic, and solution-oriented. For refund requests over $100, escalate to a supervisor.", "functions": [{"name": "lookup_order", "description": "Look up order status by order number"}, {"name": "reschedule_delivery", "description": "Reschedule a delivery"}, {"name": "file_complaint", "description": "File a formal complaint"}, {"name": "transfer_to_supervisor", "description": "Escalate to supervisor"}]}'::jsonb,
            '[{"name": "order_number", "type": "text"}, {"name": "issue_type", "type": "enum", "values": ["tracking", "reschedule", "complaint", "refund"]}, {"name": "resolution", "type": "text"}, {"name": "satisfaction_score", "type": "number"}]'::jsonb
        ),
        (
            'Dental Outbound Sales',
            'Outbound calling agent for dental practices. Promotes services, offers specials, and books appointments.',
            'Healthcare',
            ARRAY['dental', 'outbound', 'sales'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are calling on behalf of a dental practice to reach out to patients. Introduce yourself warmly, mention any current promotions or specials (teeth cleaning, whitening, check-ups), and try to schedule an appointment. If the person is a new patient, explain services offered. Be friendly but respectful of their time. If they are not interested, thank them politely and end the call.", "functions": [{"name": "book_appointment", "description": "Book a dental appointment"}, {"name": "send_promo_sms", "description": "Send promotional details via SMS"}, {"name": "add_to_callback", "description": "Add to callback list for later"}]}'::jsonb,
            '[{"name": "interested", "type": "boolean"}, {"name": "service_interest", "type": "text"}, {"name": "appointment_booked", "type": "boolean"}, {"name": "callback_requested", "type": "boolean"}]'::jsonb
        ),
        (
            'Retail Receptionist',
            'Store receptionist handling inquiries about hours, product availability, returns, and store directions.',
            'Retail',
            ARRAY['retail', 'receptionist', 'customer-service'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are the receptionist for a retail store. Help callers with store hours, product availability, return policies, current promotions, and directions. For specific product questions, transfer to the appropriate department. For online orders, direct them to the website or transfer to the e-commerce team. Be friendly, helpful, and efficient.", "functions": [{"name": "check_product", "description": "Check product availability"}, {"name": "transfer_to_department", "description": "Transfer to a specific department"}, {"name": "initiate_return", "description": "Start a return process"}]}'::jsonb,
            '[{"name": "inquiry_type", "type": "enum", "values": ["hours", "product", "return", "promotion", "directions"]}, {"name": "resolved", "type": "boolean"}]'::jsonb
        ),
        (
            'Education Program Appointment Setter',
            'Sets appointments for educational program consultations. Collects student information and preferences.',
            'Education',
            ARRAY['education', 'appointments', 'enrollment'],
            true, 'global', 'single_prompt',
            '{"system_prompt": "You are an enrollment coordinator for an educational institution. Help prospective students learn about available programs, schedule campus tours or consultations with admissions counselors, and collect basic information about their educational background and interests. Be encouraging, informative, and patient. Provide details about program durations, prerequisites, and financial aid options when asked.", "functions": [{"name": "schedule_consultation", "description": "Schedule a consultation with admissions"}, {"name": "schedule_tour", "description": "Schedule a campus tour"}, {"name": "send_brochure", "description": "Send program brochure via email"}]}'::jsonb,
            '[{"name": "program_interest", "type": "text"}, {"name": "education_level", "type": "text"}, {"name": "consultation_scheduled", "type": "boolean"}, {"name": "start_date_preference", "type": "text"}]'::jsonb
        );
    """)


def downgrade() -> None:
    op.drop_table("agent_templates")
    op.drop_table("metric_aggregates")
