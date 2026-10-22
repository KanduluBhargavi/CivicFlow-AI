"""Add historical repair targets and officer-assignment due times.

Revision ID: 20261021_0005
Revises: 20261021_0004
"""
from alembic import op
from sqlalchemy import Column, DateTime, Float, Integer, String, inspect, text

revision = "20261021_0005"
down_revision = "20261021_0004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("complaints")}
    additions = {
        "sla_target_hours": Float(),
        "sla_target_lower_hours": Float(),
        "sla_target_upper_hours": Float(),
        "sla_target_sample_size": Integer(),
        "sla_target_basis": String(80),
        "sla_target_priority": String(20),
        "officer_assignment_due_at": DateTime(timezone=True),
    }
    for name, column_type in additions.items():
        if name not in columns:
            op.add_column("complaints", Column(name, column_type, nullable=True))

    # Existing unassigned cases receive a fresh grace period after deployment;
    # they are not bulk-assigned immediately because their old wait is unknown.
    if bind.dialect.name == "postgresql":
        bind.execute(text("""
            UPDATE complaints AS c
            SET officer_assignment_due_at = CURRENT_TIMESTAMP + CASE c.priority
                WHEN 'Critical' THEN INTERVAL '30 minutes'
                WHEN 'High' THEN INTERVAL '2 hours'
                WHEN 'Medium' THEN INTERVAL '8 hours'
                ELSE INTERVAL '24 hours'
            END
            WHERE c.status = 'Assigned'
              AND c.department_id IS NOT NULL
              AND c.officer_assignment_due_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM complaint_assignments a WHERE a.complaint_id = c.complaint_id
              )
        """))
    elif bind.dialect.name == "sqlite":
        bind.execute(text("""
            UPDATE complaints
            SET officer_assignment_due_at = CASE priority
                WHEN 'Critical' THEN datetime('now', '+30 minutes')
                WHEN 'High' THEN datetime('now', '+2 hours')
                WHEN 'Medium' THEN datetime('now', '+8 hours')
                ELSE datetime('now', '+24 hours')
            END
            WHERE status = 'Assigned'
              AND department_id IS NOT NULL
              AND officer_assignment_due_at IS NULL
              AND complaint_id NOT IN (SELECT complaint_id FROM complaint_assignments)
        """))


def downgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("complaints")}
    for name in (
        "officer_assignment_due_at", "sla_target_priority", "sla_target_basis",
        "sla_target_sample_size", "sla_target_upper_hours", "sla_target_lower_hours",
        "sla_target_hours",
    ):
        if name in columns:
            op.drop_column("complaints", name)
