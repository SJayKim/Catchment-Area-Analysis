"""Unit conversion helpers for raw Seoul OpenData sales values.

The DB column ``estimated_sales.monthly_sales`` stores the raw
``THSMON_SELNG_AMT`` value from Seoul OpenData OA-15572
(상권분석서비스 추정매출). Despite the column name and the ``THSMON`` (당월)
prefix in the upstream field, the Seoul OpenData FAQ documents the value as
a **quarterly** aggregate in won:

    "분기당 매출 금액은 개인 매출액과 법인 매출액의 합산값..."

Downstream tools, agent outputs, and UI cards label this figure as
``월매출`` (monthly sales). Divide the raw DB value by
:data:`MONTHS_PER_QUARTER` at the repository read boundary to convert a
quarterly aggregate into the average monthly value those consumers expect.

This is applied only for real-mode repositories. Mock fixtures are authored
directly in monthly units and do not need conversion.
"""

from __future__ import annotations

MONTHS_PER_QUARTER = 3
