"""Repair translation_feedback columns added after the legacy schema baseline.

Revision ID: 20261021_0003
Revises: 20261019_0002
"""
from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, inspect, text
from sqlalchemy.sql import func

revision = "20261021_0003"
down_revision = "20261019_0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "translation_feedback" not in tables:
        op.create_table(
            "translation_feedback",
            Column("feedback_id", Integer, primary_key=True),
            Column("complaint_id", Integer, ForeignKey("complaints.complaint_id"), nullable=False),
            Column("citizen_id", Integer, ForeignKey("users.user_id"), nullable=False),
            Column("note", Text, nullable=False),
            Column("suggested_english", Text, nullable=True),
            Column("status", String(24), nullable=False, server_default="Open"),
            Column("reviewed_by", String(160), nullable=True),
            Column("review_note", Text, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
            Column("reviewed_at", DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_translation_feedback_complaint_id", "translation_feedback", ["complaint_id"])
        op.create_index("ix_translation_feedback_citizen_id", "translation_feedback", ["citizen_id"])
        op.create_index("ix_translation_feedback_status", "translation_feedback", ["status"])
        op.create_index("ix_translation_feedback_feedback_id", "translation_feedback", ["feedback_id"])
        return

    existing = {column["name"] for column in inspector.get_columns("translation_feedback")}
    definitions = {
        "feedback_id": (Integer(), True),
        "complaint_id": (Integer(), False),
        "citizen_id": (Integer(), False),
        "note": (Text(), False),
        "suggested_english": (Text(), False),
        "status": (String(24), False),
        "reviewed_by": (String(160), False),
        "review_note": (Text(), False),
        "created_at": (DateTime(timezone=True), False),
        "reviewed_at": (DateTime(timezone=True), False),
    }
    for name, (column_type, _) in definitions.items():
        if name not in existing:
            op.add_column("translation_feedback", Column(name, column_type, nullable=True))

    # Preserve text from known legacy feedback fields where possible.
    legacy_text = next((name for name in ("feedback_text", "feedback", "comment", "message", "description") if name in {c["name"] for c in inspector.get_columns("translation_feedback")}), None)
    note_fallback = "Legacy feedback entry; the previous schema did not store a note."
    if legacy_text:
        quoted = bind.dialect.identifier_preparer.quote(legacy_text)
        bind.execute(text(f'UPDATE translation_feedback SET note = COALESCE(NULLIF(note, \'\'), {quoted}, :fallback) WHERE note IS NULL OR note = \'\''), {"fallback": note_fallback})
    else:
        bind.execute(text("UPDATE translation_feedback SET note = :fallback WHERE note IS NULL OR note = ''"), {"fallback": note_fallback})
    bind.execute(text("UPDATE translation_feedback SET status = 'Open' WHERE status IS NULL OR status = ''"))
    bind.execute(text("UPDATE translation_feedback SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))

    # Tighten the fields required by the current ORM after legacy rows are repaired.
    alter_column = op.alter_column
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("translation_feedback") as batch:
            for name in ("note", "status", "created_at"):
                batch.alter_column(name, existing_type=definitions[name][0], nullable=False)
            batch.alter_column("status", existing_type=String(24), server_default="Open")
            batch.alter_column("created_at", existing_type=DateTime(timezone=True), server_default=func.now())
    else:
        for name in ("note", "status", "created_at"):
            alter_column("translation_feedback", name, existing_type=definitions[name][0], nullable=False)
        alter_column("translation_feedback", "status", existing_type=String(24), server_default="Open")
        alter_column("translation_feedback", "created_at", existing_type=DateTime(timezone=True), server_default=func.now())

    feedback_inspector = inspect(bind)
    refreshed = {column["name"] for column in feedback_inspector.get_columns("translation_feedback")}
    for name in ("complaint_id", "citizen_id", "status"):
        index_name = f"ix_translation_feedback_{name}"
        indexed_columns = [index.get("column_names") for index in feedback_inspector.get_indexes("translation_feedback")]
        if name in refreshed and [name] not in indexed_columns:
            op.create_index(index_name, "translation_feedback", [name], unique=False)


def downgrade():
    # Column history differs across legacy installations; an automated rollback
    # could discard user-submitted feedback. Restore a database backup instead.
    raise RuntimeError("Translation feedback repair is intentionally irreversible; restore a database backup instead.")
