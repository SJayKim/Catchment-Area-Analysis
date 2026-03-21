"""이상치 탐지기 — IQR, 시계열, Zero-ratio 기반 이상치 탐지."""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """이상치 탐지 결과."""
    is_anomaly: bool
    reason: str = ""
    value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class QualityReport:
    """데이터 품질 리포트."""
    total_records: int = 0
    anomaly_count: int = 0
    zero_ratio: float = 0.0
    null_ratio: float = 0.0
    anomalies: list[AnomalyResult] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.null_ratio < 0.05 and self.anomaly_count == 0


def detect_iqr_outlier(values: Sequence[float], target: float, *, k: float = 1.5) -> AnomalyResult:
    """IQR 기반 이상치 탐지.

    Args:
        values: 비교 대상 시계열
        target: 검사할 값
        k: IQR 배수 (기본 1.5)

    Returns:
        AnomalyResult
    """
    if len(values) < 4:
        return AnomalyResult(is_anomaly=False, reason="데이터 부족 (< 4)")

    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[3 * n // 4]
    iqr = q3 - q1

    lower = q1 - k * iqr
    upper = q3 + k * iqr

    if target < lower or target > upper:
        return AnomalyResult(
            is_anomaly=True,
            reason=f"IQR 이상치: {target:.0f} (범위: {lower:.0f}~{upper:.0f})",
            value=target,
            threshold=upper,
        )
    return AnomalyResult(is_anomaly=False, value=target)


def detect_timeseries_anomaly(
    values: Sequence[float], target: float, *, sigma_threshold: float = 3.0
) -> AnomalyResult:
    """시계열 이상치 탐지 — |현재 - 이전| > 3σ.

    Args:
        values: 직전 시계열 값들
        target: 현재 값
        sigma_threshold: 표준편차 배수 (기본 3.0)
    """
    if len(values) < 3:
        return AnomalyResult(is_anomaly=False, reason="데이터 부족")

    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    if not diffs:
        return AnomalyResult(is_anomaly=False)

    mean_diff = statistics.mean(diffs)
    if len(diffs) >= 2:
        std_diff = statistics.stdev(diffs)
    else:
        std_diff = mean_diff * 0.5

    current_diff = abs(target - values[-1])
    threshold = mean_diff + sigma_threshold * std_diff

    if std_diff > 0 and current_diff > threshold:
        return AnomalyResult(
            is_anomaly=True,
            reason=f"시계열 이상치: |{target:.0f} - {values[-1]:.0f}| = {current_diff:.0f} > {threshold:.0f}",
            value=current_diff,
            threshold=threshold,
        )
    return AnomalyResult(is_anomaly=False, value=current_diff)


def detect_percentage_change_anomaly(
    previous: float, current: float, *, max_change_pct: float = 300.0
) -> AnomalyResult:
    """급격한 변동 탐지 (300%+ 변동 플래그).

    Args:
        previous: 이전 값
        current: 현재 값
        max_change_pct: 최대 허용 변동률 (%)
    """
    if previous == 0:
        if current > 0:
            return AnomalyResult(
                is_anomaly=True, reason=f"이전 값 0에서 {current:.0f}으로 급증", value=current,
            )
        return AnomalyResult(is_anomaly=False)

    change_pct = abs(current - previous) / abs(previous) * 100
    if change_pct > max_change_pct:
        return AnomalyResult(
            is_anomaly=True,
            reason=f"변동률 {change_pct:.1f}% (허용: {max_change_pct:.0f}%)",
            value=change_pct,
            threshold=max_change_pct,
        )
    return AnomalyResult(is_anomaly=False, value=change_pct)


def check_zero_ratio(values: Sequence[Optional[float]], *, threshold: float = 0.5) -> AnomalyResult:
    """50% 이상 0값 → 데이터 품질 플래그.

    Args:
        values: 검사 대상 시퀀스
        threshold: 0값 비율 임계치 (기본 0.5 = 50%)
    """
    if not values:
        return AnomalyResult(is_anomaly=False, reason="빈 데이터")

    zero_count = sum(1 for v in values if v is not None and v == 0)
    non_null = sum(1 for v in values if v is not None)
    if non_null == 0:
        return AnomalyResult(is_anomaly=True, reason="모든 값이 NULL")

    ratio = zero_count / non_null
    if ratio >= threshold:
        return AnomalyResult(
            is_anomaly=True,
            reason=f"0값 비율 {ratio:.1%} (임계: {threshold:.0%})",
            value=ratio,
            threshold=threshold,
        )
    return AnomalyResult(is_anomaly=False, value=ratio)


def generate_quality_report(
    records: Sequence[dict], *, value_fields: Sequence[str]
) -> QualityReport:
    """데이터 셋에 대한 품질 리포트 생성.

    Args:
        records: dict 리스트 (DB row 등)
        value_fields: 검사할 수치 필드명들
    """
    report = QualityReport(total_records=len(records))
    if not records:
        return report

    total_cells = len(records) * len(value_fields)
    null_cells = 0
    zero_cells = 0

    for rec in records:
        for fld in value_fields:
            val = rec.get(fld)
            if val is None:
                null_cells += 1
            elif val == 0:
                zero_cells += 1

    report.null_ratio = null_cells / total_cells if total_cells > 0 else 0
    report.zero_ratio = zero_cells / total_cells if total_cells > 0 else 0

    # 시계열 이상치 (레코드가 3개 이상이고 첫 번째 value_field 기준)
    if len(records) >= 3 and value_fields:
        primary_field = value_fields[0]
        series = [r.get(primary_field) for r in records if r.get(primary_field) is not None]
        if len(series) >= 4:
            for i in range(3, len(series)):
                result = detect_timeseries_anomaly(series[:i], series[i])
                if result.is_anomaly:
                    report.anomalies.append(result)
                    report.anomaly_count += 1

    return report
