"""Formatting helpers for the Respond node.

Pure functions — no LLM, no I/O, no state mutation. Extracted from respond.py
to keep the node file focused on prompt assembly + streaming orchestration.
"""

from __future__ import annotations

import json


def _compute_hints(name: str, data: dict) -> str | None:
    """Auto-compute derived metrics from tool results for LLM context."""
    hints: list[str] = []
    try:
        if name == "get_floating_population" and "error" not in data:
            peak = data.get("peak_hour", 0)
            if 7 <= peak <= 9:
                peak_type = "출근형"
            elif 11 <= peak <= 13:
                peak_type = "점심형"
            elif 17 <= peak <= 19:
                peak_type = "퇴근형"
            elif 20 <= peak or peak <= 5:
                peak_type = "야간형"
            else:
                peak_type = "기타"
            hints.append(f"피크 유형: {peak_type} (피크 시간 {peak}시)")

            by_hour = data.get("by_hour", [])
            if by_hour:
                day_pop = sum(h["population"] for h in by_hour if 6 <= h["time_slot"] <= 21)
                night_pop = sum(h["population"] for h in by_hour if h["time_slot"] < 6 or h["time_slot"] > 21)
                total = day_pop + night_pop
                if total > 0:
                    hints.append(f"주간(06~21시) 비율: {day_pop / total * 100:.1f}%")

            gender = data.get("gender", {})
            m = gender.get("male_ratio", 50)
            f = gender.get("female_ratio", 50)
            diff = abs(m - f)
            if diff >= 5:
                dominant = "남성" if m > f else "여성"
                hints.append(f"성별 특성: {dominant} 우세 ({dominant} {max(m, f):.1f}%, 차이 {diff:.1f}%p)")

            age = data.get("age_distribution", {})
            if age:
                sorted_age = sorted(age.items(), key=lambda x: x[1], reverse=True)
                top1, top2 = sorted_age[0], sorted_age[1] if len(sorted_age) > 1 else (None, None)
                hints.append(f"주요 연령층: {top1[0]}({top1[1]:.1f}%)")
                if top2:
                    hints.append(f"2순위 연령층: {top2[0]}({top2[1]:.1f}%)")

        elif name == "get_estimated_sales" and "error" not in data:
            sales = data.get("total_monthly_sales", 0)
            count = data.get("total_sales_count", 0)
            weekday = data.get("weekday_sales", 0)
            weekend = data.get("weekend_sales", 0)

            if count > 0:
                avg_tx = sales / count
                hints.append(f"건당 평균 결제액: {avg_tx:,.0f}원")

            total_wk = weekday + weekend
            if total_wk > 0:
                wk_share = weekend / total_wk * 100
                hints.append(f"주말 매출 비중: {wk_share:.1f}%")
                uplift = ((weekend - weekday) / weekday * 100) if weekday > 0 else 0
                hints.append(f"주말 매출 증감률(vs 평일): {uplift:+.1f}%")

            quarterly = data.get("quarterly_sales", [])
            if len(quarterly) >= 2:
                prev = quarterly[-2].get("monthly_sales", 0)
                curr = quarterly[-1].get("monthly_sales", 0)
                if prev > 0:
                    qoq = (curr - prev) / prev * 100
                    hints.append(f"QoQ 매출 성장률: {qoq:+.1f}%")
                if len(quarterly) >= 5:
                    old = quarterly[-5].get("monthly_sales", 0)
                    if old > 0:
                        annual = (curr - old) / old * 100
                        hints.append(f"연간(4분기) 매출 성장률: {annual:+.1f}%")

            time_sales = data.get("time_sales", {})
            if time_sales:
                peak_slot = max(time_sales, key=time_sales.get)
                peak_val = time_sales[peak_slot]
                if sales > 0:
                    share = peak_val / sales * 100
                    hints.append(f"매출 피크 시간대: {peak_slot} ({share:.1f}%)")

            age_sales = data.get("age_sales", {})
            if age_sales:
                top_age = max(age_sales, key=age_sales.get)
                if sales > 0:
                    share = age_sales[top_age] / sales * 100
                    hints.append(f"매출 최다 연령층: {top_age} ({share:.1f}%)")

        elif name == "get_store_info" and "error" not in data:
            total = data.get("total_stores", 0)
            franchise = data.get("franchise_count", 0)
            opened = data.get("open_count", 0)
            closed = data.get("close_count", 0)

            if total > 0:
                fran_ratio = franchise / total * 100
                hints.append(f"프랜차이즈 비율: {fran_ratio:.1f}%")

            net = opened - closed
            net_label = "순유입" if net >= 0 else "순유출"
            hints.append(f"점포 {net_label}: {net:+d}개 (개업 {opened} - 폐업 {closed})")

            cats = data.get("top_categories", [])
            if cats and total > 0:
                top3_stores = sum(c["store_count"] for c in cats[:3])
                conc = top3_stores / total * 100
                top3_names = ", ".join(c["category_name"] for c in cats[:3])
                hints.append(f"상위 3개 업종 집중도: {conc:.1f}% ({top3_names})")

        elif name == "compare_districts" and "error" not in data:
            districts = data.get("districts", {})
            if len(districts) >= 2:
                items = list(districts.values())
                winners = {}
                for metric, label in [
                    ("floating_pop", "유동인구"),
                    ("monthly_sales", "월매출"),
                    ("close_rate", "폐업률(낮을수록 좋음)"),
                    ("store_count", "점포수"),
                ]:
                    valid = [d for d in items if metric in d and "error" not in d]
                    if valid:
                        if metric == "close_rate":
                            best = min(valid, key=lambda d: d[metric])
                        else:
                            best = max(valid, key=lambda d: d[metric])
                        winners[label] = best.get("district_name", best.get("district_code"))
                if winners:
                    hints.append("지표별 우위 상권: " + " / ".join(f"{k}: {v}" for k, v in winners.items()))

                eff_parts = []
                for d in items:
                    if "error" in d:
                        continue
                    ms = d.get("monthly_sales", 0)
                    sc = d.get("store_count", 0)
                    if sc > 0:
                        per_store = ms / sc
                        eff_parts.append(
                            f"{d.get('district_name', d.get('district_code'))}: 점포당 {per_store / 10000:,.0f}만원"
                        )
                if eff_parts:
                    hints.append("점포당 매출 효율: " + " / ".join(eff_parts))

        elif name == "get_store_history" and "error" not in data:
            bench = data.get("benchmarks", {})
            avg_cr = bench.get("seoulAvgCloseRate")
            if avg_cr:
                hints.append(f"서울 평균 폐업률: {avg_cr}% ({bench.get('districtType', '전체')} 기준)")
            trend = data.get("quarterly_trend", [])
            if len(trend) >= 2:
                latest = trend[-1]
                prev = trend[-2]
                net_latest = latest.get("open", 0) - latest.get("close", 0)
                net_prev = prev.get("open", 0) - prev.get("close", 0)
                hints.append(f"최근 분기 순증감: {net_latest:+d}개 (이전 분기: {net_prev:+d}개)")
            risk_cats = data.get("risk_categories", [])
            high_risk = [c for c in risk_cats if c.get("close_rate", 0) > 8]
            if high_risk:
                names = ", ".join(c.get("category", "?") for c in high_risk[:3])
                hints.append(f"고위험 업종(폐업률 8%+): {names}")

        elif name == "recommend_business" and "error" not in data:
            recs = data.get("recommendations", [])
            for rec in recs[:5]:
                cr = rec.get("close_rate", 0)
                if cr > 8:
                    hints.append(f"{rec.get('category_name', '?')}: 폐업률 {cr}% (고위험)")
                sc = rec.get("store_count", 0)
                if sc > 200:
                    hints.append(f"{rec.get('category_name', '?')}: 점포 {sc}개 (과포화 가능)")
            if len(recs) >= 2:
                comparison = []
                for rec in recs[:5]:
                    name_r = rec.get("category_name", "?")
                    score = rec.get("score", 0)
                    cr_r = rec.get("close_rate", 0)
                    cost = rec.get("startup_cost", 0)
                    comparison.append(f"{rec.get('rank')}위 {name_r}(점수:{score}, 폐업률:{cr_r}%, 창업비:{cost}만원)")
                hints.append("전체 추천 요약: " + " / ".join(comparison))

    except Exception:
        pass  # Hints are best-effort; never block the response

    return "\n".join(hints) if hints else None


def _format_tool_results(tool_results: dict[str, dict]) -> str:
    """Pretty-print tool results + derived hints for the LLM prompt."""
    parts: list[str] = []
    for name, data in tool_results.items():
        section = f"### {name}\n```json\n{json.dumps(data, ensure_ascii=False, default=str)[:4000]}\n```"
        hints = _compute_hints(name, data)
        if hints:
            section += f"\n\n**[파생 지표 힌트]**\n{hints}"
        parts.append(section)
    return "\n\n".join(parts)


def _format_history(history: list[dict]) -> str:
    """Format conversation history for the respond prompt."""
    lines: list[str] = []
    for t in history[-6:]:  # Last 3 turns (6 entries)
        role = "사용자" if t.get("role") == "user" else "AI"
        lines.append(f"[{role}] {t.get('content', '')}")
    return "\n".join(lines)
