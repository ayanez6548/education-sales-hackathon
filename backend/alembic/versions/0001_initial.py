"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operator_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_user_id", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="operator"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_operator_profiles_auth_user_id", "operator_profiles", ["auth_user_id"], unique=True)
    op.create_index("ix_operator_profiles_email", "operator_profiles", ["email"], unique=True)

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.String(64), nullable=False),
        sa.Column("telegram_chat_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("preferred_name", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contacts_telegram_user_id", "contacts", ["telegram_user_id"], unique=True)
    op.create_index("ix_contacts_telegram_chat_id", "contacts", ["telegram_chat_id"])

    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contents", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("modality", sa.String(80), nullable=False),
        sa.Column("duration", sa.String(80), nullable=False),
        sa.Column("schedule", sa.String(160), nullable=False),
        sa.Column("price_amount", sa.Integer(), nullable=False),
        sa.Column("price_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("authorized_link", sa.String(300), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_fictional_demo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("search_aliases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("attention_mode", sa.String(32), nullable=False, server_default="ai_active"),
        sa.Column("control_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("assigned_operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("operator_profiles.id"), nullable=True),
        sa.Column("commercial_state", sa.String(32), nullable=True),
        sa.Column("commercial_confidence", sa.Float(), nullable=True),
        sa.Column("commercial_reason", sa.String(280), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_summary", sa.Text(), nullable=True),
        sa.Column("transfer_reason", sa.String(280), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_inbound_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_ai_turn_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conversations_attention_mode", "conversations", ["attention_mode"])
    op.create_index("ix_conversations_commercial_state", "conversations", ["commercial_state"])
    op.create_index("ix_conversations_last_activity_at", "conversations", ["last_activity_at"])
    op.create_index("ix_conversations_contact_id", "conversations", ["contact_id"])

    op.create_table(
        "lead_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False, unique=True),
        sa.Column("interest_area", sa.String(160), nullable=True),
        sa.Column("experience_level", sa.String(80), nullable=True),
        sa.Column("learning_goal", sa.Text(), nullable=True),
        sa.Column("availability", sa.String(160), nullable=True),
        sa.Column("preferred_modality", sa.String(80), nullable=True),
        sa.Column("budget_note", sa.String(160), nullable=True),
        sa.Column("interested_course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("authorship", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
        sa.Column("telegram_message_id", sa.String(64), nullable=True),
        sa.Column("delivery_status", sa.String(24), nullable=False, server_default="accepted"),
        sa.Column("delivery_error", sa.String(280), nullable=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("operator_profiles.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
        sa.UniqueConstraint("telegram_chat_id", "telegram_message_id", name="uq_messages_telegram_chat_message"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    op.create_table(
        "enrollment_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(32), nullable=False, server_default="registered"),
        sa.Column("intent_key", sa.String(80), nullable=False, server_default="primary"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("contact_id", "course_id", "intent_key", name="uq_enrollment_intent"),
    )

    op.create_table(
        "telegram_updates",
        sa.Column("update_id", sa.String(64), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("expected_control_version", sa.Integer(), nullable=False),
        sa.Column("expected_inbound_seq", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leased_by", sa.String(80), nullable=True),
        sa.Column("last_error", sa.String(280), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_processing_jobs_status_available", "processing_jobs", ["status", "available_at"])
    op.create_index("ix_processing_jobs_conversation_id", "processing_jobs", ["conversation_id"])

    op.create_table(
        "outbound_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False, unique=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(280), nullable=True),
        sa.Column("telegram_chat_id", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_events_conversation_id", "audit_events", ["conversation_id"])

    op.create_table(
        "app_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_app_events_conversation_id", "app_events", ["conversation_id"])
    op.create_index("ix_app_events_event_type", "app_events", ["event_type"])
    op.create_index("ix_app_events_created_at", "app_events", ["created_at"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("operator_profiles.id"), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("operator_id", "key", name="uq_idempotency_operator_key"),
    )
    op.create_index("ix_idempotency_keys_operator_id", "idempotency_keys", ["operator_id"])

    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE contacts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lead_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE enrollment_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operator_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE courses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app_events ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION is_enabled_operator()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM operator_profiles
            WHERE auth_user_id = coalesce(auth.uid()::text, current_setting('request.jwt.claim.sub', true))
              AND enabled = true
          );
        $$;
        """
    )
    # Policies assume Supabase auth.uid(); local demo uses the service connection and bypasses RLS.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'uid' AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'auth')) THEN
            EXECUTE 'CREATE POLICY operators_read_conversations ON conversations FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_messages ON messages FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_contacts ON contacts FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_leads ON lead_profiles FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_enrollments ON enrollment_requests FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_profiles ON operator_profiles FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_courses ON courses FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_audit ON audit_events FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY operators_read_events ON app_events FOR SELECT USING (is_enabled_operator())';
            EXECUTE 'CREATE POLICY deny_anon_conversations ON conversations FOR ALL TO anon USING (false)';
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("app_events")
    op.drop_table("audit_events")
    op.drop_table("outbound_messages")
    op.drop_table("processing_jobs")
    op.drop_table("telegram_updates")
    op.drop_table("enrollment_requests")
    op.drop_table("messages")
    op.drop_table("lead_profiles")
    op.drop_table("conversations")
    op.drop_table("courses")
    op.drop_table("contacts")
    op.drop_table("operator_profiles")
