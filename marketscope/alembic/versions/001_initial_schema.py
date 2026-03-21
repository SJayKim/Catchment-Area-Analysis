"""initial schema - 10 tables for MarketScope AI

Revision ID: 001_initial
Revises:
Create Date: 2026-03-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS 확장
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- districts ---
    op.create_table(
        "districts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("district_code", sa.String(20), unique=True, nullable=False),
        sa.Column("district_name", sa.String(100), nullable=False),
        sa.Column("district_type", sa.String(20)),
        sa.Column("city_name", sa.String(50), nullable=False, server_default="서울특별시"),
        sa.Column("gu_name", sa.String(50)),
        sa.Column("dong_name", sa.String(50)),
        sa.Column("admin_dong_code", sa.String(20)),
        sa.Column("legal_dong_code", sa.String(20)),
        sa.Column("center_lat", sa.Numeric(10, 7)),
        sa.Column("center_lng", sa.Numeric(10, 7)),
        sa.Column("boundary", Geometry("POLYGON", srid=4326)),
        sa.Column("area_sqm", sa.Numeric(12, 2)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_districts_city_gu", "districts", ["city_name", "gu_name"])
    op.create_index("ix_districts_admin_dong", "districts", ["admin_dong_code"])
    op.create_index("ix_districts_boundary", "districts", ["boundary"], postgresql_using="gist")

    # --- population_stats ---
    op.create_table(
        "population_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("district_id", sa.BigInteger, sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("stat_type", sa.String(20), nullable=False),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("quarter", sa.SmallInteger),
        sa.Column("month", sa.SmallInteger),
        sa.Column("date", sa.Date),
        sa.Column("total_population", sa.BigInteger),
        sa.Column("male_population", sa.BigInteger),
        sa.Column("female_population", sa.BigInteger),
        sa.Column("age_0_9", sa.BigInteger),
        sa.Column("age_10_19", sa.BigInteger),
        sa.Column("age_20_29", sa.BigInteger),
        sa.Column("age_30_39", sa.BigInteger),
        sa.Column("age_40_49", sa.BigInteger),
        sa.Column("age_50_59", sa.BigInteger),
        sa.Column("age_60_plus", sa.BigInteger),
        sa.Column("time_00_06", sa.BigInteger),
        sa.Column("time_06_11", sa.BigInteger),
        sa.Column("time_11_14", sa.BigInteger),
        sa.Column("time_14_17", sa.BigInteger),
        sa.Column("time_17_21", sa.BigInteger),
        sa.Column("time_21_24", sa.BigInteger),
        sa.Column("day_mon", sa.BigInteger),
        sa.Column("day_tue", sa.BigInteger),
        sa.Column("day_wed", sa.BigInteger),
        sa.Column("day_thu", sa.BigInteger),
        sa.Column("day_fri", sa.BigInteger),
        sa.Column("day_sat", sa.BigInteger),
        sa.Column("day_sun", sa.BigInteger),
        sa.Column("data_source", sa.String(50)),
        sa.Column("raw_data", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("district_id", "stat_type", "year", "quarter", "month", "date", name="uq_population_period"),
    )
    op.create_index("ix_pop_district_type_year", "population_stats", ["district_id", "stat_type", "year", "quarter"])

    # --- revenue_stats ---
    op.create_table(
        "revenue_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("district_id", sa.BigInteger, sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("industry_code", sa.String(20), nullable=False),
        sa.Column("industry_name", sa.String(100)),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("quarter", sa.SmallInteger),
        sa.Column("month", sa.SmallInteger),
        sa.Column("total_revenue", sa.Numeric(18, 2)),
        sa.Column("revenue_per_store", sa.Numeric(18, 2)),
        sa.Column("transaction_count", sa.BigInteger),
        sa.Column("male_revenue", sa.Numeric(18, 2)),
        sa.Column("female_revenue", sa.Numeric(18, 2)),
        sa.Column("age_20_revenue", sa.Numeric(18, 2)),
        sa.Column("age_30_revenue", sa.Numeric(18, 2)),
        sa.Column("age_40_revenue", sa.Numeric(18, 2)),
        sa.Column("age_50_revenue", sa.Numeric(18, 2)),
        sa.Column("age_60_plus_revenue", sa.Numeric(18, 2)),
        sa.Column("day_mon_revenue", sa.Numeric(18, 2)),
        sa.Column("day_tue_revenue", sa.Numeric(18, 2)),
        sa.Column("day_wed_revenue", sa.Numeric(18, 2)),
        sa.Column("day_thu_revenue", sa.Numeric(18, 2)),
        sa.Column("day_fri_revenue", sa.Numeric(18, 2)),
        sa.Column("day_sat_revenue", sa.Numeric(18, 2)),
        sa.Column("day_sun_revenue", sa.Numeric(18, 2)),
        sa.Column("time_00_06_revenue", sa.Numeric(18, 2)),
        sa.Column("time_06_11_revenue", sa.Numeric(18, 2)),
        sa.Column("time_11_14_revenue", sa.Numeric(18, 2)),
        sa.Column("time_14_17_revenue", sa.Numeric(18, 2)),
        sa.Column("time_17_21_revenue", sa.Numeric(18, 2)),
        sa.Column("time_21_24_revenue", sa.Numeric(18, 2)),
        sa.Column("data_source", sa.String(50)),
        sa.Column("raw_data", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("district_id", "industry_code", "year", "quarter", "month", name="uq_revenue_period"),
    )
    op.create_index("ix_rev_district_industry_year", "revenue_stats", ["district_id", "industry_code", "year", "quarter"])

    # --- stores ---
    op.create_table(
        "stores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("district_id", sa.BigInteger, sa.ForeignKey("districts.id")),
        sa.Column("store_name", sa.String(200), nullable=False),
        sa.Column("branch_name", sa.String(100)),
        sa.Column("industry_code_l", sa.String(10)),
        sa.Column("industry_code_m", sa.String(10)),
        sa.Column("industry_code_s", sa.String(20)),
        sa.Column("industry_name", sa.String(100)),
        sa.Column("road_address", sa.String(300)),
        sa.Column("jibun_address", sa.String(300)),
        sa.Column("lat", sa.Numeric(10, 7)),
        sa.Column("lng", sa.Numeric(10, 7)),
        sa.Column("location", Geometry("POINT", srid=4326)),
        sa.Column("floor_info", sa.String(20)),
        sa.Column("phone", sa.String(20)),
        sa.Column("open_date", sa.Date),
        sa.Column("close_date", sa.Date),
        sa.Column("is_open", sa.Boolean, server_default="true"),
        sa.Column("data_source", sa.String(50)),
        sa.Column("raw_data", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_stores_location", "stores", ["location"], postgresql_using="gist")
    op.create_index("ix_stores_industry", "stores", ["industry_code_s"])
    op.create_index("ix_stores_district_industry", "stores", ["district_id", "industry_code_s"])

    # --- transit_stats ---
    op.create_table(
        "transit_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("station_name", sa.String(100), nullable=False),
        sa.Column("line_name", sa.String(50)),
        sa.Column("station_code", sa.String(20)),
        sa.Column("transit_type", sa.String(20), nullable=False),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("month", sa.SmallInteger, nullable=False),
        sa.Column("boarding_total", sa.BigInteger),
        sa.Column("alighting_total", sa.BigInteger),
        sa.Column("daily_avg_boarding", sa.Integer),
        sa.Column("daily_avg_alighting", sa.Integer),
        sa.Column("lat", sa.Numeric(10, 7)),
        sa.Column("lng", sa.Numeric(10, 7)),
        sa.Column("nearest_district_id", sa.BigInteger, sa.ForeignKey("districts.id")),
        sa.Column("data_source", sa.String(50)),
        sa.Column("raw_data", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("station_name", "line_name", "transit_type", "year", "month", name="uq_transit_period"),
    )
    op.create_index("ix_transit_station_year_month", "transit_stats", ["station_name", "year", "month"])

    # --- code_mappings ---
    op.create_table(
        "code_mappings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("mapping_type", sa.String(30), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_code", sa.String(20)),
        sa.Column("parent_name", sa.String(100)),
        sa.Column("related_code", sa.String(20)),
        sa.Column("related_name", sa.String(100)),
        sa.Column("level", sa.SmallInteger),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("mapping_type", "code", name="uq_code_mapping"),
    )
    op.create_index("ix_code_mapping_type_code", "code_mappings", ["mapping_type", "code"])

    # --- unit_prices ---
    op.create_table(
        "unit_prices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("industry_code", sa.String(20), nullable=False),
        sa.Column("industry_name", sa.String(100)),
        sa.Column("avg_unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_unit_price", sa.Numeric(12, 2)),
        sa.Column("max_unit_price", sa.Numeric(12, 2)),
        sa.Column("source", sa.String(100)),
        sa.Column("reference_year", sa.SmallInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("industry_code", "reference_year", name="uq_unit_price"),
    )

    # --- startup_costs ---
    op.create_table(
        "startup_costs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("industry_code", sa.String(20), nullable=False),
        sa.Column("industry_name", sa.String(100)),
        sa.Column("size_sqm", sa.Integer),
        sa.Column("interior_cost", sa.Numeric(14, 2)),
        sa.Column("equipment_cost", sa.Numeric(14, 2)),
        sa.Column("deposit", sa.Numeric(14, 2)),
        sa.Column("monthly_rent", sa.Numeric(14, 2)),
        sa.Column("premium", sa.Numeric(14, 2)),
        sa.Column("etc_cost", sa.Numeric(14, 2)),
        sa.Column("total_min", sa.Numeric(14, 2)),
        sa.Column("total_max", sa.Numeric(14, 2)),
        sa.Column("source", sa.String(100)),
        sa.Column("reference_year", sa.SmallInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("industry_code", "reference_year", "size_sqm", name="uq_startup_cost"),
    )

    # --- analysis_sessions ---
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), unique=True, nullable=False),
        sa.Column("user_query", sa.Text, nullable=False),
        sa.Column("analysis_mode", sa.String(20), nullable=False, server_default="basic"),
        sa.Column("target_district_code", sa.String(20)),
        sa.Column("target_industry_code", sa.String(20)),
        sa.Column("target_address", sa.String(300)),
        sa.Column("target_lat", sa.Numeric(10, 7)),
        sa.Column("target_lng", sa.Numeric(10, 7)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_summary", postgresql.JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("execution_time_ms", sa.Integer),
        sa.Column("agent_details", postgresql.JSONB),
        sa.Column("llm_tokens_used", sa.Integer),
        sa.Column("llm_cost_usd", sa.Numeric(8, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- collection_logs ---
    op.create_table(
        "collection_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("collector_name", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("params", postgresql.JSONB),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("records_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("response_size_bytes", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_collection_log_collector_date", "collection_logs", ["collector_name", "created_at"])


def downgrade() -> None:
    op.drop_table("collection_logs")
    op.drop_table("analysis_sessions")
    op.drop_table("startup_costs")
    op.drop_table("unit_prices")
    op.drop_table("code_mappings")
    op.drop_table("transit_stats")
    op.drop_table("stores")
    op.drop_table("revenue_stats")
    op.drop_table("population_stats")
    op.drop_table("districts")
    op.execute("DROP EXTENSION IF EXISTS postgis")
