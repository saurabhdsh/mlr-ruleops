"""ticket HITL gate columns

Revision ID: 0003_hitl_gate
Revises: 0002_configuration_matrix
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

from app.db.base import Base
from app import models  # noqa: F401

revision = "0003_hitl_gate"
down_revision = "0002_configuration_matrix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("tickets")} if inspector.has_table("tickets") else set()
    if "hitl_gate" not in cols:
        op.add_column("tickets", sa.Column("hitl_gate", sa.String(64), nullable=True))
    if "autonomy_tier" not in cols:
        op.add_column("tickets", sa.Column("autonomy_tier", sa.String(32), nullable=True))
    if "expected_target_rule" not in cols:
        op.add_column("tickets", sa.Column("expected_target_rule", sa.String(160), nullable=True))
    if "match_confidence" not in cols:
        op.add_column("tickets", sa.Column("match_confidence", sa.Float(), nullable=True))
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    op.drop_column("tickets", "match_confidence")
    op.drop_column("tickets", "expected_target_rule")
    op.drop_column("tickets", "autonomy_tier")
    op.drop_column("tickets", "hitl_gate")
