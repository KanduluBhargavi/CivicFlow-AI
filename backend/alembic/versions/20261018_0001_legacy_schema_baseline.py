"""Create missing CivicFlow tables and safely extend existing legacy tables.

Revision ID: 20261018_0001
Revises:
"""
from alembic import op
from sqlalchemy import inspect

from app.database import Base
from app.models.complaint import Complaint
from app.models.user import User
from app.models.department import Department
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_event import ComplaintEvent
from app.models.complaint_support import ComplaintSupport
from app.models.complaint_escalation import ComplaintEscalation
from app.models.in_app_notification import InAppNotification
from app.models.complaint_deletion import ComplaintDeletion
from app.models.translation_feedback import TranslationFeedback
from app.models.contact import Feedback

revision = "20261018_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Add absent fields as nullable for safe upgrades of non-empty legacy DBs.
    # New tables are created below with the full current constraints.
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present or column.primary_key:
                continue
            new_column = column.copy()
            new_column.nullable = True
            op.add_column(table.name, new_column)

    Base.metadata.create_all(bind=bind, checkfirst=True)
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(bind=bind, checkfirst=True)


def downgrade():
    raise RuntimeError("This legacy baseline is intentionally irreversible; restore a database backup instead.")
