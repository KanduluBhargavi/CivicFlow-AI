"""Add a required category to translation feedback.

Revision ID: 20261021_0004
Revises: 20261021_0003
"""
from alembic import op
from sqlalchemy import Column, String, inspect, text

revision = "20261021_0004"
down_revision = "20261021_0003"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("translation_feedback")}
    if "issue_type" not in columns:
        op.add_column("translation_feedback", Column("issue_type", String(40), nullable=True))
    bind.execute(text("UPDATE translation_feedback SET issue_type = 'translation' WHERE issue_type IS NULL OR issue_type = ''"))
    op.alter_column(
        "translation_feedback", "issue_type", existing_type=String(40),
        nullable=False, server_default="translation",
    )


def downgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("translation_feedback")}
    if "issue_type" in columns:
        op.drop_column("translation_feedback", "issue_type")
