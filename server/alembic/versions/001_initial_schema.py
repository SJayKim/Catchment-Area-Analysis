"""initial schema - all Phase 0 tables

Revision ID: 001
Revises:
Create Date: 2026-03-25
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- districts ---
    op.create_table(
        "districts",
        sa.Column("district_code", sa.String(20), primary_key=True),
        sa.Column("district_name", sa.String(100), nullable=False),
        sa.Column("district_type", sa.String(20), nullable=False),
        sa.Column(
            "boundary",
            geoalchemy2.types.Geometry(geometry_type="POLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column(
            "center_point",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("gu_code", sa.String(10), nullable=True),
        sa.Column("dong_code", sa.String(10), nullable=True),
        sa.Column("data_quarter", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_districts_boundary ON districts USING gist (boundary)")

    # --- floating_population ---
    op.create_table(
        "floating_population",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "district_code",
            sa.String(20),
            sa.ForeignKey("districts.district_code"),
            nullable=False,
        ),
        sa.Column("quarter", sa.String(10), nullable=False),
        sa.Column("time_slot", sa.SmallInteger, nullable=False),
        sa.Column("total_pop", sa.Integer, server_default="0"),
        sa.Column("male_pop", sa.Integer, server_default="0"),
        sa.Column("female_pop", sa.Integer, server_default="0"),
        sa.Column("age_10_pop", sa.Integer, server_default="0"),
        sa.Column("age_20_pop", sa.Integer, server_default="0"),
        sa.Column("age_30_pop", sa.Integer, server_default="0"),
        sa.Column("age_40_pop", sa.Integer, server_default="0"),
        sa.Column("age_50_pop", sa.Integer, server_default="0"),
        sa.Column("age_60_plus_pop", sa.Integer, server_default="0"),
        sa.UniqueConstraint("district_code", "quarter", "time_slot", name="uq_fp_district_quarter_ts"),
    )
    op.create_index("idx_fp_district_quarter", "floating_population", ["district_code", "quarter"])

    # --- estimated_sales ---
    op.create_table(
        "estimated_sales",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "district_code",
            sa.String(20),
            sa.ForeignKey("districts.district_code"),
            nullable=False,
        ),
        sa.Column("category_code", sa.String(20), nullable=False),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("quarter", sa.String(10), nullable=False),
        sa.Column("monthly_sales", sa.BigInteger),
        sa.Column("sales_count", sa.Integer),
        sa.Column("weekday_sales", sa.BigInteger),
        sa.Column("weekend_sales", sa.BigInteger),
        sa.Column("male_sales", sa.BigInteger),
        sa.Column("female_sales", sa.BigInteger),
        sa.Column("age_10_sales", sa.BigInteger),
        sa.Column("age_20_sales", sa.BigInteger),
        sa.Column("age_30_sales", sa.BigInteger),
        sa.Column("age_40_sales", sa.BigInteger),
        sa.Column("age_50_sales", sa.BigInteger),
        sa.Column("age_60_plus_sales", sa.BigInteger),
        sa.Column("time_1_sales", sa.BigInteger),
        sa.Column("time_2_sales", sa.BigInteger),
        sa.Column("time_3_sales", sa.BigInteger),
        sa.Column("time_4_sales", sa.BigInteger),
        sa.Column("time_5_sales", sa.BigInteger),
        sa.Column("time_6_sales", sa.BigInteger),
        sa.UniqueConstraint(
            "district_code",
            "category_code",
            "quarter",
            name="uq_es_district_category_quarter",
        ),
    )
    op.create_index(
        "idx_es_district_category",
        "estimated_sales",
        ["district_code", "category_code", "quarter"],
    )

    # --- stores ---
    op.create_table(
        "stores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "district_code",
            sa.String(20),
            sa.ForeignKey("districts.district_code"),
            nullable=False,
        ),
        sa.Column("category_code", sa.String(20), nullable=False),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("quarter", sa.String(10), nullable=False),
        sa.Column("store_count", sa.Integer),
        sa.Column("open_count", sa.Integer),
        sa.Column("close_count", sa.Integer),
        sa.Column("franchise_count", sa.Integer),
        sa.UniqueConstraint(
            "district_code",
            "category_code",
            "quarter",
            name="uq_stores_district_category_quarter",
        ),
    )
    op.create_index("idx_stores_district_quarter", "stores", ["district_code", "quarter"])

    # --- store_history ---
    op.create_table(
        "store_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "district_code",
            sa.String(20),
            sa.ForeignKey("districts.district_code"),
            nullable=False,
        ),
        sa.Column("address", sa.String(200)),
        sa.Column("category_code", sa.String(20)),
        sa.Column("category_name", sa.String(100)),
        sa.Column("open_date", sa.Date),
        sa.Column("close_date", sa.Date),
        sa.Column("duration_months", sa.Integer),
    )
    op.create_index("idx_sh_district", "store_history", ["district_code"])

    # --- resident_population ---
    op.create_table(
        "resident_population",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "district_code",
            sa.String(20),
            sa.ForeignKey("districts.district_code"),
            nullable=False,
        ),
        sa.Column("quarter", sa.String(10), nullable=False),
        sa.Column("pop_type", sa.String(10), nullable=False),
        sa.Column("age_group", sa.String(10), nullable=False),
        sa.Column("gender", sa.String(1), nullable=False),
        sa.Column("population", sa.Integer, nullable=False),
        sa.UniqueConstraint(
            "district_code",
            "quarter",
            "pop_type",
            "age_group",
            "gender",
            name="uq_rp_district_quarter_type_age_gender",
        ),
    )
    op.create_index("idx_rp_district_quarter", "resident_population", ["district_code", "quarter"])

    # --- chat_sessions ---
    op.create_table(
        "chat_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("district_code", sa.String(20)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("tool_name", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- category_metadata ---
    op.create_table(
        "category_metadata",
        sa.Column("category_code", sa.String(20), primary_key=True),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("major_category", sa.String(50)),
        sa.Column("avg_startup_cost", sa.Integer),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("category_metadata")
    op.drop_table("resident_population")
    op.drop_table("store_history")
    op.drop_table("stores")
    op.drop_table("estimated_sales")
    op.drop_table("floating_population")
    op.drop_table("districts")
    op.execute("DROP EXTENSION IF EXISTS postgis")
