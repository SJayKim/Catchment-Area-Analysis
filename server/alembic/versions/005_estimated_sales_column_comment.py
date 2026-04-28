"""Document estimated_sales.monthly_sales raw-unit semantics

Revision ID: 005
Revises: 004
Create Date: 2026-04-24

컬럼명 `monthly_sales` 와 실제 저장 단위(분기 누적 원)가 불일치. Repository
층에서 `_enrich_sales` 가 `/3` 환산 후 월 매출로 노출. ETL 담당자가 컬럼명만
보고 추가/중복 환산하는 함정을 방지하기 위해 column comment 로 원본 의미를
코드 레벨 상수와 함께 기록한다.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN estimated_sales.monthly_sales IS "
        "'SOURCE: Seoul OpenData THSMON_SELNG_AMT. UNIT: KRW. "
        "AGGREGATION: quarterly cumulative (not monthly despite column name). "
        "Divide by 3 via QUARTER_TO_MONTH_DIVISOR for monthly estimate. "
        "See server/repositories/real/estimated_sales.py::_enrich_sales.'"
    )


def downgrade() -> None:
    op.execute("COMMENT ON COLUMN estimated_sales.monthly_sales IS NULL")
