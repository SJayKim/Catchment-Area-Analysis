from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("districts.district_code"), nullable=False
    )
    category_code: Mapped[str] = mapped_column(String(20), nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False)
    store_count: Mapped[int | None] = mapped_column(Integer)
    open_count: Mapped[int | None] = mapped_column(Integer)
    close_count: Mapped[int | None] = mapped_column(Integer)
    franchise_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint(
            "district_code", "category_code", "quarter",
            name="uq_stores_district_category_quarter",
        ),
        Index("idx_stores_district_quarter", "district_code", "quarter"),
    )


class StoreHistory(Base):
    __tablename__ = "store_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("districts.district_code"), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(200))
    category_code: Mapped[str | None] = mapped_column(String(20))
    category_name: Mapped[str | None] = mapped_column(String(100))
    open_date: Mapped[date | None] = mapped_column(Date)
    close_date: Mapped[date | None] = mapped_column(Date)
    duration_months: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_sh_district", "district_code"),
    )
