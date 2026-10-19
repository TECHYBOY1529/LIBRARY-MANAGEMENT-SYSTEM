"""Add authentication version for session revocation.

Revision ID: 6b8b6d312f41
Revises: 4a72bc16d903
"""
from alembic import op
import sqlalchemy as sa


revision = "6b8b6d312f41"
down_revision = "4a72bc16d903"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade():
    op.drop_column("users", "auth_version")
