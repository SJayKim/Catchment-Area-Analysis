from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base


class District(Base):
    __tablename__ = "districts"

    district_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    district_name: Mapped[str] = mapped_column(String(100), nullable=False)
    district_type: Mapped[str] = mapped_column(String(20), nullable=False)
    boundary: Mapped[str | None] = mapped_column(Geometry("POLYGON", srid=4326))
    center_point: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    gu_code: Mapped[str | None] = mapped_column(String(10))
    dong_code: Mapped[str | None] = mapped_column(String(10))
    data_quarter: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (Index("idx_districts_boundary", "boundary", postgresql_using="gist"),)
