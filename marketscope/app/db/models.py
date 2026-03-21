"""MarketScope AI SQLAlchemy ORM 모델."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """모든 ORM 모델의 기본 클래스."""
    pass


class TimestampMixin:
    """created_at, updated_at 자동 관리 믹스인."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# D0-2: 핵심 테이블
# ---------------------------------------------------------------------------


class District(TimestampMixin, Base):
    """상권 기본 정보 (SEMAS 상권 단위)."""

    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="SEMAS 상권코드")
    district_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="상권명")
    district_type: Mapped[Optional[str]] = mapped_column(String(20), comment="상권유형 (골목/발달/전통시장/관광특구)")
    city_name: Mapped[str] = mapped_column(String(50), nullable=False, default="서울특별시")
    gu_name: Mapped[Optional[str]] = mapped_column(String(50), comment="구 이름")
    dong_name: Mapped[Optional[str]] = mapped_column(String(50), comment="행정동 이름")
    admin_dong_code: Mapped[Optional[str]] = mapped_column(String(20), comment="행정동코드")
    legal_dong_code: Mapped[Optional[str]] = mapped_column(String(20), comment="법정동코드")
    center_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), comment="중심 위도")
    center_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), comment="중심 경도")
    boundary: Mapped[Optional[str]] = mapped_column(
        Geometry("POLYGON", srid=4326),
        comment="상권 경계 (PostGIS POLYGON)",
    )
    area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), comment="면적 (㎡)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    population_stats: Mapped[list["PopulationStat"]] = relationship(back_populates="district", lazy="selectin")
    revenue_stats: Mapped[list["RevenueStat"]] = relationship(back_populates="district", lazy="selectin")
    stores: Mapped[list["Store"]] = relationship(back_populates="district", lazy="selectin")

    __table_args__ = (
        Index("ix_districts_city_gu", "city_name", "gu_name"),
        Index("ix_districts_admin_dong", "admin_dong_code"),
        Index("ix_districts_boundary", "boundary", postgresql_using="gist"),
    )

    def __repr__(self) -> str:
        return f"<District {self.district_code} {self.district_name}>"


class PopulationStat(TimestampMixin, Base):
    """인구 통계 (유동인구/생활인구/주민/직장인구)."""

    __tablename__ = "population_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("districts.id"), nullable=False)
    stat_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="floating(유동)|living(생활)|resident(주민)|worker(직장)",
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="분기 (1~4), NULL이면 연간")
    month: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="월 (1~12)")
    date: Mapped[Optional[datetime]] = mapped_column(Date, comment="일별 데이터일 경우")

    total_population: Mapped[Optional[int]] = mapped_column(BigInteger)
    male_population: Mapped[Optional[int]] = mapped_column(BigInteger)
    female_population: Mapped[Optional[int]] = mapped_column(BigInteger)

    age_0_9: Mapped[Optional[int]] = mapped_column(BigInteger)
    age_10_19: Mapped[Optional[int]] = mapped_column(BigInteger)
    age_20_29: Mapped[Optional[int]] = mapped_column(BigInteger)
    age_30_39: Mapped[Optional[int]] = mapped_column(BigInteger)
    age_40_49: Mapped[Optional[int]] = mapped_column(BigInteger)
    age_50_59: Mapped[Optional[int]] = mapped_column(BigInteger)
    age_60_plus: Mapped[Optional[int]] = mapped_column(BigInteger)

    time_00_06: Mapped[Optional[int]] = mapped_column(BigInteger, comment="시간대별 인구: 00~06시")
    time_06_11: Mapped[Optional[int]] = mapped_column(BigInteger, comment="06~11시")
    time_11_14: Mapped[Optional[int]] = mapped_column(BigInteger, comment="11~14시")
    time_14_17: Mapped[Optional[int]] = mapped_column(BigInteger, comment="14~17시")
    time_17_21: Mapped[Optional[int]] = mapped_column(BigInteger, comment="17~21시")
    time_21_24: Mapped[Optional[int]] = mapped_column(BigInteger, comment="21~24시")

    day_mon: Mapped[Optional[int]] = mapped_column(BigInteger, comment="요일별 인구: 월")
    day_tue: Mapped[Optional[int]] = mapped_column(BigInteger)
    day_wed: Mapped[Optional[int]] = mapped_column(BigInteger)
    day_thu: Mapped[Optional[int]] = mapped_column(BigInteger)
    day_fri: Mapped[Optional[int]] = mapped_column(BigInteger)
    day_sat: Mapped[Optional[int]] = mapped_column(BigInteger)
    day_sun: Mapped[Optional[int]] = mapped_column(BigInteger)

    data_source: Mapped[Optional[str]] = mapped_column(String(50), comment="데이터 출처 (SEMAS|SEOUL|KOSIS)")
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, comment="원본 응답 보관")

    # Relationships
    district: Mapped["District"] = relationship(back_populates="population_stats")

    __table_args__ = (
        Index("ix_pop_district_type_year", "district_id", "stat_type", "year", "quarter"),
        UniqueConstraint(
            "district_id", "stat_type", "year", "quarter", "month", "date",
            name="uq_population_period",
        ),
    )

    def __repr__(self) -> str:
        return f"<PopulationStat district={self.district_id} {self.stat_type} {self.year}Q{self.quarter}>"


class RevenueStat(TimestampMixin, Base):
    """매출 통계 (추정매출, 카드매출)."""

    __tablename__ = "revenue_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("districts.id"), nullable=False)
    industry_code: Mapped[str] = mapped_column(String(20), nullable=False, comment="업종코드 (소분류)")
    industry_name: Mapped[Optional[str]] = mapped_column(String(100), comment="업종명")
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[Optional[int]] = mapped_column(SmallInteger)
    month: Mapped[Optional[int]] = mapped_column(SmallInteger)

    total_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), comment="총 매출 (원)")
    revenue_per_store: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), comment="점포당 매출")
    transaction_count: Mapped[Optional[int]] = mapped_column(BigInteger, comment="건수")

    male_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    female_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    age_20_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    age_30_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    age_40_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    age_50_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    age_60_plus_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    day_mon_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    day_tue_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    day_wed_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    day_thu_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    day_fri_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    day_sat_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    day_sun_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    time_00_06_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    time_06_11_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    time_11_14_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    time_14_17_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    time_17_21_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    time_21_24_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    district: Mapped["District"] = relationship(back_populates="revenue_stats")

    __table_args__ = (
        Index("ix_rev_district_industry_year", "district_id", "industry_code", "year", "quarter"),
        UniqueConstraint(
            "district_id", "industry_code", "year", "quarter", "month",
            name="uq_revenue_period",
        ),
    )


class Store(TimestampMixin, Base):
    """점포 정보."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("districts.id"))
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_name: Mapped[Optional[str]] = mapped_column(String(100))
    industry_code_l: Mapped[Optional[str]] = mapped_column(String(10), comment="대분류 코드")
    industry_code_m: Mapped[Optional[str]] = mapped_column(String(10), comment="중분류 코드")
    industry_code_s: Mapped[Optional[str]] = mapped_column(String(20), comment="소분류 코드")
    industry_name: Mapped[Optional[str]] = mapped_column(String(100))

    road_address: Mapped[Optional[str]] = mapped_column(String(300))
    jibun_address: Mapped[Optional[str]] = mapped_column(String(300))
    lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    location: Mapped[Optional[str]] = mapped_column(
        Geometry("POINT", srid=4326),
        comment="PostGIS POINT",
    )
    floor_info: Mapped[Optional[str]] = mapped_column(String(20), comment="층 정보")
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    open_date: Mapped[Optional[datetime]] = mapped_column(Date, comment="개업일")
    close_date: Mapped[Optional[datetime]] = mapped_column(Date, comment="폐업일")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)

    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    district: Mapped[Optional["District"]] = relationship(back_populates="stores")

    __table_args__ = (
        Index("ix_stores_location", "location", postgresql_using="gist"),
        Index("ix_stores_industry", "industry_code_s"),
        Index("ix_stores_district_industry", "district_id", "industry_code_s"),
    )


class TransitStat(TimestampMixin, Base):
    """교통 통계 (지하철 승하차, 버스)."""

    __tablename__ = "transit_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_name: Mapped[Optional[str]] = mapped_column(String(50), comment="노선명")
    station_code: Mapped[Optional[str]] = mapped_column(String(20))
    transit_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="subway|bus")

    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    boarding_total: Mapped[Optional[int]] = mapped_column(BigInteger, comment="승차 합계")
    alighting_total: Mapped[Optional[int]] = mapped_column(BigInteger, comment="하차 합계")
    daily_avg_boarding: Mapped[Optional[int]] = mapped_column(Integer, comment="일평균 승차")
    daily_avg_alighting: Mapped[Optional[int]] = mapped_column(Integer, comment="일평균 하차")

    lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    nearest_district_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("districts.id"))

    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_transit_station_year_month", "station_name", "year", "month"),
        UniqueConstraint(
            "station_name", "line_name", "transit_type", "year", "month",
            name="uq_transit_period",
        ),
    )


class CodeMapping(TimestampMixin, Base):
    """코드 매핑 (행정동↔법정동↔상권코드)."""

    __tablename__ = "code_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mapping_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="admin_dong|legal_dong|district|industry",
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_code: Mapped[Optional[str]] = mapped_column(String(20), comment="상위 코드")
    parent_name: Mapped[Optional[str]] = mapped_column(String(100))
    related_code: Mapped[Optional[str]] = mapped_column(String(20), comment="연계 코드 (행정동↔법정동)")
    related_name: Mapped[Optional[str]] = mapped_column(String(100))
    level: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="계층 (대/중/소 = 1/2/3)")
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, comment="추가 속성")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_code_mapping_type_code", "mapping_type", "code"),
        UniqueConstraint("mapping_type", "code", name="uq_code_mapping"),
    )


class UnitPrice(TimestampMixin, Base):
    """업종별 객단가 (수동 입력/크롤링)."""

    __tablename__ = "unit_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    industry_code: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_name: Mapped[Optional[str]] = mapped_column(String(100))
    avg_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="평균 객단가 (원)")
    min_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    max_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    source: Mapped[Optional[str]] = mapped_column(String(100), comment="출처 (배민/요기요/수동)")
    reference_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("industry_code", "reference_year", name="uq_unit_price"),
    )


class StartupCost(TimestampMixin, Base):
    """업종별 창업 비용 (수동 입력)."""

    __tablename__ = "startup_costs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    industry_code: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_name: Mapped[Optional[str]] = mapped_column(String(100))
    size_sqm: Mapped[Optional[int]] = mapped_column(Integer, comment="기준 면적 (㎡)")
    interior_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="인테리어 (원)")
    equipment_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="설비/장비 (원)")
    deposit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="보증금 (원)")
    monthly_rent: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="월세 (원)")
    premium: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="권리금 (원)")
    etc_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="기타비용 (원)")
    total_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="최소 총 창업비용")
    total_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), comment="최대 총 창업비용")
    source: Mapped[Optional[str]] = mapped_column(String(100))
    reference_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("industry_code", "reference_year", "size_sqm", name="uq_startup_cost"),
    )


class AnalysisSession(TimestampMixin, Base):
    """분석 세션 (사용자 요청 히스토리)."""

    __tablename__ = "analysis_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, comment="UUID")
    user_query: Mapped[str] = mapped_column(Text, nullable=False, comment="사용자 원본 쿼리")
    analysis_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="basic")

    target_district_code: Mapped[Optional[str]] = mapped_column(String(20))
    target_industry_code: Mapped[Optional[str]] = mapped_column(String(20))
    target_address: Mapped[Optional[str]] = mapped_column(String(300))
    target_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    target_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_summary: Mapped[Optional[dict]] = mapped_column(JSONB, comment="FinalReport JSON")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)

    agent_details: Mapped[Optional[dict]] = mapped_column(JSONB, comment="에이전트별 결과 상세")
    llm_tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    llm_cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))


class CollectionLog(TimestampMixin, Base):
    """데이터 수집 이력."""

    __tablename__ = "collection_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    collector_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="semas|seoul|kosis")
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="success|failed|partial")
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    response_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_collection_log_collector_date", "collector_name", "created_at"),
    )
