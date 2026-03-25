"""Database loader with UPSERT support and batch processing."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.config import settings
from server.models.population import FloatingPopulation, ResidentPopulation
from server.models.sales import EstimatedSales
from server.models.store import Store

logger = logging.getLogger(__name__)


class DataLoader:
    """Handles bulk UPSERT operations for ETL data."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self.batch_size = settings.etl_batch_size

    async def upsert_districts(self, rows: list[dict]) -> int:
        """Upsert districts with PostGIS coordinate transform (EPSG:5181 → 4326).

        Uses raw SQL because GeoAlchemy2 UPSERT with ST_Transform requires text().
        """
        if not rows:
            return 0

        inserted = 0
        async with self.session_factory() as session:
            for row in rows:
                boundary_expr = "NULL"
                center_expr = "NULL"

                if row.get("boundary_wkt"):
                    boundary_expr = (
                        f"ST_Transform(ST_GeomFromText(:boundary_wkt, 5181), 4326)"
                    )
                if row.get("center_wkt"):
                    center_expr = (
                        f"ST_Transform(ST_GeomFromText(:center_wkt, 5181), 4326)"
                    )

                sql = text(f"""
                    INSERT INTO districts (
                        district_code, district_name, district_type,
                        boundary, center_point,
                        gu_code, dong_code, data_quarter
                    ) VALUES (
                        :district_code, :district_name, :district_type,
                        {boundary_expr}, {center_expr},
                        :gu_code, :dong_code, :data_quarter
                    )
                    ON CONFLICT (district_code) DO UPDATE SET
                        district_name = EXCLUDED.district_name,
                        district_type = EXCLUDED.district_type,
                        boundary = EXCLUDED.boundary,
                        center_point = EXCLUDED.center_point,
                        gu_code = EXCLUDED.gu_code,
                        dong_code = EXCLUDED.dong_code,
                        data_quarter = EXCLUDED.data_quarter
                """)

                params: dict[str, Any] = {
                    "district_code": row["district_code"],
                    "district_name": row["district_name"],
                    "district_type": row["district_type"],
                    "gu_code": row.get("gu_code"),
                    "dong_code": row.get("dong_code"),
                    "data_quarter": row["data_quarter"],
                }
                if row.get("boundary_wkt"):
                    params["boundary_wkt"] = row["boundary_wkt"]
                if row.get("center_wkt"):
                    params["center_wkt"] = row["center_wkt"]

                await session.execute(sql, params)
                inserted += 1

            await session.commit()

        logger.info(f"[districts] upserted {inserted} rows")
        return inserted

    async def upsert_floating_pop(self, rows: list[dict]) -> int:
        """Batch upsert floating population data."""
        return await self._batch_upsert(
            FloatingPopulation,
            rows,
            conflict_columns=["district_code", "quarter", "time_slot"],
            constraint_name="uq_fp_district_quarter_ts",
        )

    async def upsert_estimated_sales(self, rows: list[dict]) -> int:
        """Batch upsert estimated sales data."""
        return await self._batch_upsert(
            EstimatedSales,
            rows,
            conflict_columns=["district_code", "category_code", "quarter"],
            constraint_name="uq_es_district_category_quarter",
        )

    async def upsert_stores(self, rows: list[dict]) -> int:
        """Batch upsert stores data."""
        return await self._batch_upsert(
            Store,
            rows,
            conflict_columns=["district_code", "category_code", "quarter"],
            constraint_name="uq_stores_district_category_quarter",
        )

    async def upsert_resident_pop(self, rows: list[dict]) -> int:
        """Batch upsert resident/worker population data."""
        return await self._batch_upsert(
            ResidentPopulation,
            rows,
            conflict_columns=["district_code", "quarter", "pop_type", "age_group", "gender"],
            constraint_name="uq_rp_district_quarter_type_age_gender",
        )

    async def _batch_upsert(
        self,
        model: type,
        rows: list[dict],
        conflict_columns: list[str],
        constraint_name: str,
    ) -> int:
        """Generic batch UPSERT using PostgreSQL ON CONFLICT."""
        if not rows:
            return 0

        table_name = model.__tablename__
        total = 0

        for i in range(0, len(rows), self.batch_size):
            batch = rows[i : i + self.batch_size]
            async with self.session_factory() as session:
                stmt = pg_insert(model).values(batch)

                # Build SET clause: update all columns except conflict columns and 'id'
                update_cols = {
                    col.name: stmt.excluded[col.name]
                    for col in model.__table__.columns
                    if col.name not in conflict_columns and col.name != "id"
                }

                stmt = stmt.on_conflict_do_update(
                    constraint=constraint_name,
                    set_=update_cols,
                )

                await session.execute(stmt)
                await session.commit()
                total += len(batch)

            logger.info(f"[{table_name}] batch {i // self.batch_size + 1}: {len(batch)} rows")

        logger.info(f"[{table_name}] total upserted: {total} rows")
        return total
