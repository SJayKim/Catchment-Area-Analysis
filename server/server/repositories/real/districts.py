"""Real district repository — PostGIS-backed queries."""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.agent.utils.entity_matching import (
    RankedCandidate,
    pick_best,
    rank_candidates,
)

logger = logging.getLogger(__name__)


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

    # 상권명이 아닌 일반 키워드 (과잉 매칭 방지)
    _STOPWORDS = frozenset(
        {
            "카페",
            "커피",
            "한식",
            "중식",
            "일식",
            "양식",
            "분식",
            "치킨",
            "편의점",
            "미용",
            "약국",
            "주점",
            "제과",
            "음식점",
            "식당",
            "서울",
            "서울시",
            "상권",
            "분석",
            "추천",
            "비교",
            "위험",
            "리스크",
            "폐업",
            "매출",
            "유동인구",
            "인구",
            "업종",
            "시뮬레이션",
            "히트맵",
            "리포트",
            "요약",
            "현황",
            "정보",
            "안녕",
            "감사",
            "도움",
            "질문",
        }
    )

    _PARTICLES = (
        "에서는",
        "이랑은",
        "에서",
        "부터",
        "까지",
        "처럼",
        "만큼",
        "이랑",
        "하고",
        "에게",
        "한테",
        "보다",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "에",
        "도",
        "로",
        "의",
        "와",
        "과",
        "랑",
        "서",
    )

    # Common location suffixes in Korean place names
    _LOCATION_SUFFIXES = ("입구", "역", "앞", "사거리", "네거리")

    @classmethod
    def _candidate_words(cls, message: str) -> list[str]:
        """Extract candidate words with Korean particle stripping + stopword filtering.

        Also generates shortened forms by stripping location suffixes
        (e.g. "홍대입구" -> "홍대") to match DB names that may differ.

        2-character candidates are preserved (e.g. "성수", "종로") to support
        short-form district references — filtering to 3+ chars lives in the
        matcher, not here.
        """
        words = re.findall(r"[\w가-힣]{2,10}", message)
        candidates: list[str] = []
        seen: set[str] = set()
        for word in words:
            stripped = (
                word[: -len(p)]
                for p in cls._PARTICLES
                if word.endswith(p) and len(word) > len(p) and len(word) - len(p) >= 2
            )
            for cand in (word, *stripped):
                if cand in cls._STOPWORDS or cand in seen:
                    continue
                seen.add(cand)
                candidates.append(cand)

        # Generate extra candidates by stripping location suffixes
        extra: list[str] = []
        for cand in list(candidates):
            for suffix in cls._LOCATION_SUFFIXES:
                if cand.endswith(suffix) and len(cand) - len(suffix) >= 2:
                    short = cand[: -len(suffix)]
                    if short not in cls._STOPWORDS and short not in seen:
                        seen.add(short)
                        extra.append(short)
        candidates.extend(extra)
        return candidates

    async def detect_district_by_name(self, message: str) -> dict | None:
        """Single-district detection (first candidate wins).

        Delegates to the same pool + ranker as ``detect_districts_in_message``
        so 2-char queries (e.g. "성수") are handled consistently. Returns the
        first candidate that clears ``TOP1_MIN``; ambiguous matches are still
        returned (with the ``alternatives`` key) so the caller can decide.
        """
        for candidate in self._candidate_words(message):
            pool = await self._fetch_match_pool(candidate)
            if not pool:
                continue
            ranked = rank_candidates(candidate, pool)
            best, alts, is_ambiguous = pick_best(ranked)
            if best is None:
                continue
            result: dict = {
                "code": best.code,
                "name": best.name,
                "score": round(best.score, 4),
                "ambiguous": is_ambiguous,
            }
            if alts:
                result["alternatives"] = [a.to_dict() for a in alts]
            return result
        return None

    async def _fetch_match_pool(self, candidate: str) -> list[tuple[str, str, str | None]]:
        """Fetch every (code, name, type) row that *might* match a candidate.

        We pull a deliberately loose pool (prefix + contains + reverse prefix)
        and let the Python-side ranker score. 1,650 rows is tiny, so a single
        index-backed ``ilike`` is the fastest path even when the candidate is
        2 chars.
        """
        from sqlalchemy import literal, or_, select

        from server.models.district import District

        conditions = [District.district_name == candidate]
        # Prefix — always allowed (including 2-char queries like "성수").
        conditions.append(District.district_name.ilike(f"{candidate}%"))
        if len(candidate) >= 3:
            conditions.append(District.district_name.ilike(f"%{candidate}%"))
            conditions.append(literal(candidate).ilike(District.district_name + "%"))

        stmt = (
            select(District.district_code, District.district_name, District.district_type)
            .where(or_(*conditions))
            .limit(25)
        )
        async with self._sf() as session:
            rows = (await session.execute(stmt)).all()
        return [(r.district_code, r.district_name, r.district_type) for r in rows]

    async def detect_districts_in_message(self, message: str) -> list[dict]:
        """Find all districts referenced in the message with ranking + abstention.

        Behaviour (GAP-A, 2026-04-23):
        - Accepts 2-char queries via prefix-only matching (e.g. "성수" → "성수역_2").
        - Uses hybrid string similarity to rank candidates when the raw DB
          ilike matches multiple rows.
        - Marks an entry ``ambiguous=True`` when Top1 and Top2 are within the
          abstention band (``CLOSE_DELTA``). ``alternatives`` carries up to 2
          runner-up candidates so the Planner/Actor can surface a choice card.

        Returns ``list[dict]`` max 5 — each dict has ``{code, name, score,
        ambiguous, alternatives}``. Back-compat: callers that only read
        ``code`` / ``name`` keep working.
        """
        found: list[dict] = []
        seen_codes: set[str] = set()
        candidates = self._candidate_words(message)
        logger.info(
            "detect_districts: msg=%r candidates=%s",
            message[:80],
            candidates,
        )

        for candidate in candidates:
            if len(found) >= 5:
                break
            pool = await self._fetch_match_pool(candidate)
            if not pool:
                logger.info("detect_districts: %r → empty pool (no rows match)", candidate)
                continue

            ranked = rank_candidates(candidate, pool)
            best, alts, is_ambiguous = pick_best(ranked)
            if best is None:
                top = ranked[0] if ranked else None
                logger.info(
                    "detect_districts: %r → below TOP1_MIN (top=%s)",
                    candidate,
                    top.to_dict() if top else None,
                )
                continue
            if best.code in seen_codes:
                continue
            logger.info(
                "detect_districts: %r → %s score=%.3f alts=%d ambiguous=%s",
                candidate,
                f"{best.code}/{best.name}",
                best.score,
                len(alts),
                is_ambiguous,
            )

            entry: dict = {
                "code": best.code,
                "name": best.name,
                "score": round(best.score, 4),
                "ambiguous": is_ambiguous,
            }
            if is_ambiguous or alts:
                entry["alternatives"] = [a.to_dict() for a in alts]
            found.append(entry)
            seen_codes.add(best.code)

            if is_ambiguous:
                logger.info(
                    "detect_districts: ambiguous match for %r → %s vs %s (Δ=%.3f)",
                    candidate,
                    best.to_dict(),
                    alts[0].to_dict() if alts else None,
                    best.score - (alts[0].score if alts else 0.0),
                )

        return found

    # Typed accessor retained for callers that only want top-1 codes; keeps
    # the Planner's existing ``m["code"] for m in multi`` comprehension valid.
    _rank_candidates = staticmethod(rank_candidates)
    _pick_best = staticmethod(pick_best)
    _RankedCandidate = RankedCandidate

    async def list_districts(
        self, search: str | None, district_type: str | None, limit: int, offset: int
    ) -> tuple[int, list[dict]]:
        from geoalchemy2.functions import ST_X, ST_Y
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
                items.append(
                    {
                        "district_code": district.district_code,
                        "district_name": district.district_name,
                        "district_type": district.district_type,
                        "gu_code": district.gu_code,
                        "dong_code": district.dong_code,
                        "data_quarter": district.data_quarter,
                        "center_lng": cx,
                        "center_lat": cy,
                    }
                )
            return total, items

    async def get_district_detail(self, code: str) -> dict | None:
        from geoalchemy2.functions import ST_X, ST_Y, ST_AsGeoJSON
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
        from geoalchemy2.functions import ST_X, ST_Y, ST_AsGeoJSON
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
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "district_code": code,
                            "district_name": name,
                            "district_type": d_type,
                            "data_quarter": quarter,
                            "center": [cx, cy] if cx is not None and cy is not None else None,
                        },
                        "geometry": geometry,
                    }
                )
            return {"type": "FeatureCollection", "features": features}
