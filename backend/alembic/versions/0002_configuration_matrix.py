"""configuration matrix

Revision ID: 0002_configuration_matrix
Revises: 0001_initial
Create Date: 2026-09-05
"""

from alembic import op

from app.db.base import Base
from app import models  # noqa: F401

revision = "0002_configuration_matrix"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    op.drop_table("configuration_matrix")
