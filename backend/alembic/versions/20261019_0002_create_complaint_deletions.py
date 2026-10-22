"""Create the complaint deletion audit table when it is missing.

Revision ID: 20261019_0002
Revises: 20261018_0001
"""
from alembic import op
from sqlalchemy import inspect, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

revision = "20261019_0002"
down_revision = "20261018_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "complaint_deletions" not in inspector.get_table_names():
        op.create_table(
            "complaint_deletions",
            Column("deletion_id", Integer, primary_key=True),
            Column("complaint_id", Integer, nullable=False),
            Column("deleted_by", String(length=160), nullable=False),
            Column("reason", Text, nullable=False),
            Column("deleted_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        )
        op.create_index("ix_complaint_deletions_deletion_id", "complaint_deletions", ["deletion_id"], unique=False)
        op.create_index("ix_complaint_deletions_complaint_id", "complaint_deletions", ["complaint_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    if "complaint_deletions" in inspect(bind).get_table_names():
        op.drop_table("complaint_deletions")
