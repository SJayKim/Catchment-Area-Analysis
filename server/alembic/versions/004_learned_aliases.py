"""learned_aliases table for GAP-B runtime alias expansion

Revision ID: 004
Revises: 003
Create Date: 2026-04-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS learned_aliases (
            alias        VARCHAR(200) PRIMARY KEY,
            code         VARCHAR(20)  NOT NULL REFERENCES category_metadata(category_code)
                                                 ON DELETE CASCADE,
            confidence   REAL         NOT NULL,
            source       VARCHAR(50)  NOT NULL,
            hit_count    INTEGER      NOT NULL DEFAULT 1,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            last_used_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT learned_aliases_confidence_range
                CHECK (confidence >= 0 AND confidence <= 1)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_learned_aliases_code
            ON learned_aliases(code)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_learned_aliases_code")
    op.execute("DROP TABLE IF EXISTS learned_aliases")
