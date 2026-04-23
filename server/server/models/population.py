from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base


class FloatingPopulation(Base):
    __tablename__ = "floating_population"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(String(20), ForeignKey("districts.district_code"), nullable=False)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False)
    time_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_pop: Mapped[int] = mapped_column(Integer, default=0)
    male_pop: Mapped[int] = mapped_column(Integer, default=0)
    female_pop: Mapped[int] = mapped_column(Integer, default=0)
    age_10_pop: Mapped[int] = mapped_column(Integer, default=0)
    age_20_pop: Mapped[int] = mapped_column(Integer, default=0)
    age_30_pop: Mapped[int] = mapped_column(Integer, default=0)
    age_40_pop: Mapped[int] = mapped_column(Integer, default=0)
    age_50_pop: Mapped[int] = mapped_column(Integer, default=0)
    age_60_plus_pop: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("district_code", "quarter", "time_slot", name="uq_fp_district_quarter_ts"),
        Index("idx_fp_district_quarter", "district_code", "quarter"),
    )


class ResidentPopulation(Base):
    __tablename__ = "resident_population"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(String(20), ForeignKey("districts.district_code"), nullable=False)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False)
    pop_type: Mapped[str] = mapped_column(String(10), nullable=False)  # resident / worker
    age_group: Mapped[str] = mapped_column(String(10), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    population: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "district_code",
            "quarter",
            "pop_type",
            "age_group",
            "gender",
            name="uq_rp_district_quarter_type_age_gender",
        ),
        Index("idx_rp_district_quarter", "district_code", "quarter"),
    )
