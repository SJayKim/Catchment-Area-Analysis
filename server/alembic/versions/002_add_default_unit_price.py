"""add default_unit_price to category_metadata

Revision ID: 002
Revises: 001
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Major-category → default unit price (원)
_UNIT_PRICES: dict[str, int] = {
    "외식": 12000,
    "서비스": 25000,
    "소매": 15000,
}


def upgrade() -> None:
    op.add_column(
        "category_metadata",
        sa.Column("default_unit_price", sa.Integer(), nullable=True),
    )

    # Backfill unit prices by major_category
    for major, price in _UNIT_PRICES.items():
        op.execute(
            sa.text(
                "UPDATE category_metadata SET default_unit_price = :price "
                "WHERE major_category = :major AND default_unit_price IS NULL"
            ).bindparams(price=price, major=major)
        )


def downgrade() -> None:
    op.drop_column("category_metadata", "default_unit_price")
