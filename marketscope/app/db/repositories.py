"""데이터 접근 레이어 — Repository 패턴 CRUD."""

from __future__ import annotations

from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Base,
    CodeMapping,
    CollectionLog,
    District,
    PopulationStat,
    RevenueStat,
    Store,
    TransitStat,
)

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """제네릭 비동기 CRUD Repository."""

    def __init__(self, session: AsyncSession, model: Type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id_: int) -> Optional[T]:
        return await self.session.get(self.model, id_)

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def create_many(self, entities: list[T]) -> list[T]:
        self.session.add_all(entities)
        await self.session.flush()
        return entities

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()


class DistrictRepository(BaseRepository[District]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, District)

    async def get_by_code(self, district_code: str) -> Optional[District]:
        stmt = select(District).where(District.district_code == district_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_dong_code(self, admin_dong_code: str) -> Optional[District]:
        stmt = select(District).where(District.admin_dong_code == admin_dong_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name(self, name: str, *, limit: int = 20) -> Sequence[District]:
        stmt = (
            select(District)
            .where(District.district_name.ilike(f"%{name}%"))
            .where(District.is_active.is_(True))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_gu(self, gu_name: str) -> Sequence[District]:
        stmt = (
            select(District)
            .where(District.gu_name == gu_name)
            .where(District.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class PopulationRepository(BaseRepository[PopulationStat]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PopulationStat)

    async def get_by_district(
        self,
        district_id: int,
        stat_type: str,
        *,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
    ) -> Sequence[PopulationStat]:
        stmt = select(PopulationStat).where(
            PopulationStat.district_id == district_id,
            PopulationStat.stat_type == stat_type,
        )
        if year:
            stmt = stmt.where(PopulationStat.year == year)
        if quarter:
            stmt = stmt.where(PopulationStat.quarter == quarter)
        stmt = stmt.order_by(PopulationStat.year.desc(), PopulationStat.quarter.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest(self, district_id: int, stat_type: str) -> Optional[PopulationStat]:
        stmt = (
            select(PopulationStat)
            .where(
                PopulationStat.district_id == district_id,
                PopulationStat.stat_type == stat_type,
            )
            .order_by(PopulationStat.year.desc(), PopulationStat.quarter.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class RevenueRepository(BaseRepository[RevenueStat]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RevenueStat)

    async def get_by_district_industry(
        self,
        district_id: int,
        industry_code: str,
        *,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
    ) -> Sequence[RevenueStat]:
        stmt = select(RevenueStat).where(
            RevenueStat.district_id == district_id,
            RevenueStat.industry_code == industry_code,
        )
        if year:
            stmt = stmt.where(RevenueStat.year == year)
        if quarter:
            stmt = stmt.where(RevenueStat.quarter == quarter)
        stmt = stmt.order_by(RevenueStat.year.desc(), RevenueStat.quarter.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest(self, district_id: int, industry_code: str) -> Optional[RevenueStat]:
        stmt = (
            select(RevenueStat)
            .where(
                RevenueStat.district_id == district_id,
                RevenueStat.industry_code == industry_code,
            )
            .order_by(RevenueStat.year.desc(), RevenueStat.quarter.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class StoreRepository(BaseRepository[Store]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Store)

    async def get_by_district(
        self,
        district_id: int,
        *,
        industry_code: Optional[str] = None,
        only_open: bool = True,
    ) -> Sequence[Store]:
        stmt = select(Store).where(Store.district_id == district_id)
        if industry_code:
            stmt = stmt.where(Store.industry_code_s == industry_code)
        if only_open:
            stmt = stmt.where(Store.is_open.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_district_industry(
        self, district_id: int, industry_code: str, *, only_open: bool = True
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Store)
            .where(Store.district_id == district_id, Store.industry_code_s == industry_code)
        )
        if only_open:
            stmt = stmt.where(Store.is_open.is_(True))
        result = await self.session.execute(stmt)
        return result.scalar_one()


class TransitRepository(BaseRepository[TransitStat]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TransitStat)

    async def get_by_station(
        self, station_name: str, *, year: Optional[int] = None, month: Optional[int] = None
    ) -> Sequence[TransitStat]:
        stmt = select(TransitStat).where(TransitStat.station_name == station_name)
        if year:
            stmt = stmt.where(TransitStat.year == year)
        if month:
            stmt = stmt.where(TransitStat.month == month)
        stmt = stmt.order_by(TransitStat.year.desc(), TransitStat.month.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CodeMappingRepository(BaseRepository[CodeMapping]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CodeMapping)

    async def get_by_type_and_code(self, mapping_type: str, code: str) -> Optional[CodeMapping]:
        stmt = select(CodeMapping).where(
            CodeMapping.mapping_type == mapping_type,
            CodeMapping.code == code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_type(self, mapping_type: str, *, active_only: bool = True) -> Sequence[CodeMapping]:
        stmt = select(CodeMapping).where(CodeMapping.mapping_type == mapping_type)
        if active_only:
            stmt = stmt.where(CodeMapping.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def resolve_dong_to_district(self, admin_dong_code: str) -> Optional[str]:
        """행정동코드 → 상권코드 변환 (related_code 경유)."""
        mapping = await self.get_by_type_and_code("admin_dong", admin_dong_code)
        if mapping and mapping.related_code:
            return mapping.related_code
        return None


class CollectionLogRepository(BaseRepository[CollectionLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CollectionLog)

    async def get_latest_by_collector(self, collector_name: str) -> Optional[CollectionLog]:
        stmt = (
            select(CollectionLog)
            .where(CollectionLog.collector_name == collector_name)
            .order_by(CollectionLog.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str, *, limit: int = 50) -> Sequence[CollectionLog]:
        stmt = (
            select(CollectionLog)
            .where(CollectionLog.status == status)
            .order_by(CollectionLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
