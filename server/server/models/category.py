from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base


class CategoryMetadata(Base):
    __tablename__ = "category_metadata"

    category_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    major_category: Mapped[str | None] = mapped_column(String(50))  # 외식/서비스/소매
    avg_startup_cost: Mapped[int | None] = mapped_column()  # 평균 창업비용 (만원)
    default_unit_price: Mapped[int | None] = mapped_column()  # 기본 객단가 (원)
    aliases: Mapped[str | None] = mapped_column(String(500))  # 별칭 (쉼표 구분)
