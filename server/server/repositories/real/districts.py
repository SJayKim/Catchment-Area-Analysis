"""Real district repository — PostGIS-backed queries."""

from __future__ import annotations

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RealDistrictRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_district_meta(self, district_code: str) -> dict | None:
        from sqlalchemy import select

        from server.models.district import District

        async with self._sf() as session:
            row = (
                await session.execute(
                    select(District.district_name, District.district_type).where(
                        District.district_code == district_code
                    )
                )
            ).one_or_none()
            if row is None:
                return None
            return {"name": row.district_name, "type": row.district_type}

    async def resolve_district(self, district_code: str) -> dict | None:
        from geoalchemy2.functions import ST_X, ST_Y
        from sqlalchemy import select

        from server.models.district import District

        async with self._sf() as session:
            result = await session.execute(
                select(
                    District.district_name,
                    District.district_type,
                    District.data_quarter,
                    ST_Y(District.center_point).label("lat"),
                    ST_X(District.center_point).label("lng"),
                ).where(District.district_code == district_code)
            )
            row = result.first()
            if not row:
                return None
            center = None
            if row.lat is not None and row.lng is not None:
                center = {"lat": float(row.lat), "lng": float(row.lng)}
            return {
                "name": row.district_name,
                "type": row.district_type,
                "quarter": row.data_quarter,
                "center": center,
            }

    async def detect_district_by_name(self, message: str) -> dict | None:
        from sqlalchemy import select

        from server.models.district import District

        _PARTICLES = [
            "에서는", "이랑은", "에서", "부터", "까지", "처럼", "만큼",
            "이랑", "하고", "에게", "한테", "보다",
            "은", "는", "이", "가", "을", "를", "에", "도", "로", "의",
            "와", "과", "랑", "서",
        ]

        words = re.findall(r"[\w가-힣]{2,10}", message)
        async with self._sf() as session:
            for word in words:
                candidates = [word]
                for p in _PARTICLES:
                    if word.endswith(p) and len(word) > len(p):
                        stem = word[: -len(p)]
                        if len(stem) >= 2:
                            candidates.append(stem)
                for candidate in candidates:
                    result = await session.execute(
                        select(District.district_code, District.district_name)
                        .where(District.district_name.ilike(f"%{candidate}%"))
                        .limit(1)
                    )
                    row = result.first()
                    if row:
                        return {"code": row.district_code, "name": row.district_name}
        return None

    async def list_districts(
        self, search: str | None, district_type: str | None, limit: int, offset: int
    ) -> tuple[int, list[dict]]:
        from geoalchemy2.functions import ST_AsGeoJSON, ST_X, ST_Y
        from sqlalchemy import func, select

        from server.models.district import District

        async with self._sf() as session:
            conditions = []
            if search:
                conditions.append(District.district_name.ilike(f"%{search}%"))
            if district_type:
                conditions.append(District.district_type == district_type)

            count_query = select(func.count(District.district_code))
            if conditions:
                count_query = count_query.where(*conditions)
            total = (await session.execute(count_query)).scalar_one()

            base_query = select(
                District,
                ST_X(District.center_point).label("cx"),
                ST_Y(District.center_point).label("cy"),
            )
            if conditions:
                base_query = base_query.where(*conditions)
            base_query = base_query.order_by(District.district_name).limit(limit).offset(offset)

            rows = (await session.execute(base_query)).all()
            items = []
            for row in rows:
                district, cx, cy = row
                items.append({
                    "district_code": district.district_code,
                    "district_name": district.district_name,
                    "district_type": district.district_type,
                    "gu_code": district.gu_code,
                    "dong_code": district.dong_code,
                    "data_quarter": district.data_quarter,
                    "center_lng": cx,
                    "center_lat": cy,
                })
            return total, items

    async def get_district_detail(self, code: str) -> dict | None:
        from geoalchemy2.functions import ST_AsGeoJSON, ST_X, ST_Y
        from sqlalchemy import select

        from server.models.district import District

        async with self._sf() as session:
            query = select(
                District,
                ST_AsGeoJSON(District.boundary).label("geojson"),
                ST_X(District.center_point).label("cx"),
                ST_Y(District.center_point).label("cy"),
            ).where(District.district_code == code)
            row = (await session.execute(query)).first()
            if row is None:
                return None
            district, geojson_str, cx, cy = row
            polygon = json.loads(geojson_str) if geojson_str else None
            return {
                "district_code": district.district_code,
                "district_name": district.district_name,
                "district_type": district.district_type,
                "gu_code": district.gu_code,
                "dong_code": district.dong_code,
                "data_quarter": district.data_quarter,
                "center_lng": cx,
                "center_lat": cy,
                "polygon": polygon,
            }

    async def get_polygons_geojson(self, bounds: str | None) -> dict:
        from geoalchemy2.functions import ST_AsGeoJSON, ST_X, ST_Y
        from sqlalchemy import func, select

        from server.models.district import District

        async with self._sf() as session:
            query = select(
                District.district_code,
                District.district_name,
                District.district_type,
                District.data_quarter,
                ST_AsGeoJSON(District.boundary).label("geojson"),
                ST_X(District.center_point).label("cx"),
                ST_Y(District.center_point).label("cy"),
            )
            if bounds:
                parts = bounds.split(",")
                if len(parts) == 4:
                    sw_lat, sw_lng, ne_lat, ne_lng = (float(p.strip()) for p in parts)
                    envelope = func.ST_MakeEnvelope(sw_lng, sw_lat, ne_lng, ne_lat, 4326)
                    query = query.where(func.ST_Intersects(District.boundary, envelope))
            query = query.limit(500)
            rows = (await session.execute(query)).all()

            features = []
            for row in rows:
                code, name, d_type, quarter, geojson_str, cx, cy = row
                if not geojson_str:
                    continue
                geometry = json.loads(geojson_str)
                features.append({
                    "type": "Feature",
                    "properties": {
                        "district_code": code,
                        "district_name": name,
                        "district_type": d_type,
                        "data_quarter": quarter,
                        "center": [cx, cy] if cx is not None and cy is not None else None,
                    },
                    "geometry": geometry,
                })
            return {"type": "FeatureCollection", "features": features}
