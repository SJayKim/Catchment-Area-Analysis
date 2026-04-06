"""add aliases to category_metadata

Revision ID: 003
Revises: 002
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS guards against dev DBs that were manually patched before
    # this migration existed (self-introduced drift in Step 3 hardcoding fix).
    op.execute(
        "ALTER TABLE category_metadata "
        "ADD COLUMN IF NOT EXISTS aliases VARCHAR(500)"
    )


def downgrade() -> None:
    op.drop_column("category_metadata", "aliases")
