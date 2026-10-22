"""Add auditable officer delay requests and manager review."""
from alembic import op
import sqlalchemy as sa

revision = "20261021_0006"
down_revision = "20261021_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "complaint_delay_requests",
        sa.Column("request_id", sa.Integer(), primary_key=True),
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.complaint_id"), nullable=False),
        sa.Column("officer_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("blocker_category", sa.String(length=40), nullable=False),
        sa.Column("requested_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="Pending Head Review"),
        sa.Column("manager_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("followup_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_complaint_delay_requests_request_id", "complaint_delay_requests", ["request_id"])
    op.create_index("ix_complaint_delay_requests_complaint_id", "complaint_delay_requests", ["complaint_id"])
    op.create_index("ix_complaint_delay_requests_officer_id", "complaint_delay_requests", ["officer_id"])
    op.create_index("ix_complaint_delay_requests_status", "complaint_delay_requests", ["status"])


def downgrade():
    op.drop_index("ix_complaint_delay_requests_status", table_name="complaint_delay_requests")
    op.drop_index("ix_complaint_delay_requests_officer_id", table_name="complaint_delay_requests")
    op.drop_index("ix_complaint_delay_requests_complaint_id", table_name="complaint_delay_requests")
    op.drop_index("ix_complaint_delay_requests_request_id", table_name="complaint_delay_requests")
    op.drop_table("complaint_delay_requests")
