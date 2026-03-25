from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base


class EstimatedSales(Base):
    __tablename__ = "estimated_sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("districts.district_code"), nullable=False
    )
    category_code: Mapped[str] = mapped_column(String(20), nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False)
    monthly_sales: Mapped[int | None] = mapped_column(BigInteger)
    sales_count: Mapped[int | None] = mapped_column(Integer)
    weekday_sales: Mapped[int | None] = mapped_column(BigInteger)
    weekend_sales: Mapped[int | None] = mapped_column(BigInteger)
    male_sales: Mapped[int | None] = mapped_column(BigInteger)
    female_sales: Mapped[int | None] = mapped_column(BigInteger)
    age_10_sales: Mapped[int | None] = mapped_column(BigInteger)
    age_20_sales: Mapped[int | None] = mapped_column(BigInteger)
    age_30_sales: Mapped[int | None] = mapped_column(BigInteger)
    age_40_sales: Mapped[int | None] = mapped_column(BigInteger)
    age_50_sales: Mapped[int | None] = mapped_column(BigInteger)
    age_60_plus_sales: Mapped[int | None] = mapped_column(BigInteger)
    time_1_sales: Mapped[int | None] = mapped_column(BigInteger)  # 00~06
    time_2_sales: Mapped[int | None] = mapped_column(BigInteger)  # 06~11
    time_3_sales: Mapped[int | None] = mapped_column(BigInteger)  # 11~14
    time_4_sales: Mapped[int | None] = mapped_column(BigInteger)  # 14~17
    time_5_sales: Mapped[int | None] = mapped_column(BigInteger)  # 17~21
    time_6_sales: Mapped[int | None] = mapped_column(BigInteger)  # 21~24

    __table_args__ = (
        UniqueConstraint(
            "district_code", "category_code", "quarter",
            name="uq_es_district_category_quarter",
        ),
        Index("idx_es_district_category", "district_code", "category_code", "quarter"),
    )
