from sqlalchemy import func, select

from server.config import settings
from server.services.cache import cache_service


async def recommend_business(
    district_code: str,
    budget: int | None = None,
    preference: str | None = None,
) -> dict:
    """Recommend top 5 business categories for a district.

    Uses a scoring formula: (per-store sales) x (age match) x (1 - close rate) / competition.
    Optionally filters by budget and category group preference.
    """
    cache_key = f"recommend:{district_code}:{budget or 'all'}:{preference or 'all'}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    if settings.use_mock:
        from server.agent.tools.mock_data import get_recommendations
        result = get_recommendations(district_code, budget, preference)
        await cache_service.set(cache_key, result, ttl=86400)
        return result

    from server.models.base import async_session
    from server.models.category import CategoryMetadata
    from server.models.population import FloatingPopulation
    from server.models.sales import EstimatedSales
    from server.models.store import Store

    async with async_session() as session:
        # --- Determine latest quarter ---
        latest_q = await session.execute(
            select(Store.quarter)
            .where(Store.district_code == district_code)
            .order_by(Store.quarter.desc())
            .limit(1)
        )
        quarter = latest_q.scalar_one_or_none()
        if quarter is None:
            return {"error": "해당 상권의 데이터가 없습니다.", "district_code": district_code}

        # --- Get all categories with store data in this district ---
        cat_stmt = (
            select(
                Store.category_code,
                Store.category_name,
                Store.store_count,
                Store.open_count,
                Store.close_count,
            )
            .where(
                Store.district_code == district_code,
                Store.quarter == quarter,
                Store.store_count > 0,
            )
        )
        cat_rows = (await session.execute(cat_stmt)).all()
        if not cat_rows:
            return {"error": "점포 데이터가 없습니다.", "district_code": district_code}

        total_stores_in_district = sum(int(r.store_count or 0) for r in cat_rows)

        # --- Get sales data for each category ---
        sales_stmt = (
            select(
                EstimatedSales.category_code,
                EstimatedSales.monthly_sales,
                EstimatedSales.age_10_sales,
                EstimatedSales.age_20_sales,
                EstimatedSales.age_30_sales,
                EstimatedSales.age_40_sales,
                EstimatedSales.age_50_sales,
                EstimatedSales.age_60_plus_sales,
            )
            .where(
                EstimatedSales.district_code == district_code,
                EstimatedSales.quarter == quarter,
            )
        )
        sales_rows = (await session.execute(sales_stmt)).all()
        sales_map = {row.category_code: row for row in sales_rows}

        # --- Get floating population age distribution ---
        fp_stmt = (
            select(
                func.sum(FloatingPopulation.age_10_pop).label("a10"),
                func.sum(FloatingPopulation.age_20_pop).label("a20"),
                func.sum(FloatingPopulation.age_30_pop).label("a30"),
                func.sum(FloatingPopulation.age_40_pop).label("a40"),
                func.sum(FloatingPopulation.age_50_pop).label("a50"),
                func.sum(FloatingPopulation.age_60_plus_pop).label("a60"),
            )
            .where(FloatingPopulation.district_code == district_code)
            .where(FloatingPopulation.quarter == quarter)
        )
        fp_result = await session.execute(fp_stmt)
        fp_row = fp_result.one_or_none()

        pop_by_age = {}
        pop_total = 0
        if fp_row:
            pop_by_age = {
                "10대": int(fp_row.a10 or 0),
                "20대": int(fp_row.a20 or 0),
                "30대": int(fp_row.a30 or 0),
                "40대": int(fp_row.a40 or 0),
                "50대": int(fp_row.a50 or 0),
                "60대 이상": int(fp_row.a60 or 0),
            }
            pop_total = sum(pop_by_age.values())

        # --- Category metadata (startup cost, group) ---
        meta_stmt = select(
            CategoryMetadata.category_code,
            CategoryMetadata.avg_startup_cost,
            CategoryMetadata.major_category,
        )
        meta_rows = (await session.execute(meta_stmt)).all()
        meta_map = {r.category_code: r for r in meta_rows}

        # --- Compute scores ---
        raw_scores = []

        for cat_row in cat_rows:
            code = cat_row.category_code
            name = cat_row.category_name
            store_count = int(cat_row.store_count or 0)
            close_count = int(cat_row.close_count or 0)

            sales_data = sales_map.get(code)
            if not sales_data or not sales_data.monthly_sales:
                continue

            monthly_sales = int(sales_data.monthly_sales or 0)
            per_store_sales = monthly_sales / store_count if store_count else 0

            # Competition density
            competition = store_count / total_stores_in_district if total_stores_in_district else 1

            # Close rate
            close_rate = close_count / store_count if store_count else 0

            # Age match
            age_sales = {
                "10대": int(sales_data.age_10_sales or 0),
                "20대": int(sales_data.age_20_sales or 0),
                "30대": int(sales_data.age_30_sales or 0),
                "40대": int(sales_data.age_40_sales or 0),
                "50대": int(sales_data.age_50_sales or 0),
                "60대 이상": int(sales_data.age_60_plus_sales or 0),
            }
            total_age_sales = sum(age_sales.values())

            age_match = 0.5
            if total_age_sales > 0 and pop_total > 0:
                sorted_ages = sorted(age_sales.items(), key=lambda x: x[1], reverse=True)
                target_ages = []
                cumulative = 0
                for age, sales in sorted_ages:
                    target_ages.append(age)
                    cumulative += sales / total_age_sales
                    if cumulative >= 0.7:
                        break

                target_pop = sum(pop_by_age.get(a, 0) for a in target_ages)
                age_match = target_pop / pop_total

            raw_score = (per_store_sales * age_match * (1 - close_rate)) / max(competition, 0.01)

            reasons = []
            reasons.append(f"점포당 월매출 {per_store_sales / 10000:.0f}만원")
            if age_match >= 0.5:
                reasons.append(f"타겟 고객 매칭률 {age_match * 100:.0f}%")
            reasons.append(f"경쟁 점포 {store_count}개 (밀집도 {competition * 100:.1f}%)")
            if close_rate < 0.05:
                reasons.append(f"폐업률 낮음 ({close_rate * 100:.1f}%)")
            elif close_rate > 0.1:
                reasons.append(f"폐업률 주의 ({close_rate * 100:.1f}%)")

            meta = meta_map.get(code)
            startup_cost = int(meta.avg_startup_cost or 0) if meta else None

            raw_scores.append({
                "category_code": code,
                "category_name": name,
                "raw_score": raw_score,
                "per_store_sales": int(per_store_sales),
                "store_count": store_count,
                "close_rate": round(close_rate * 100, 1),
                "age_match": round(age_match * 100, 1),
                "monthly_sales": monthly_sales,
                "reasons": reasons,
                "startup_cost": startup_cost,
                "category_group": meta.major_category if meta else None,
            })

        # --- Filter ---
        filtered = raw_scores
        budget_filtered = False

        if preference:
            pref_filtered = [s for s in filtered if s.get("category_group") and preference in s["category_group"]]
            if pref_filtered:
                filtered = pref_filtered

        if budget:
            budget_result = [s for s in filtered if s.get("startup_cost") is not None and s["startup_cost"] <= budget]
            if budget_result:
                filtered = budget_result
                budget_filtered = True

        # --- Normalize scores 0~100 ---
        if filtered:
            values = [s["raw_score"] for s in filtered]
            min_val, max_val = min(values), max(values)
            spread = max_val - min_val if max_val != min_val else 1
            for s in filtered:
                s["score"] = round((s["raw_score"] - min_val) / spread * 100, 1)
        else:
            filtered = raw_scores

        top5 = sorted(filtered, key=lambda x: x.get("score", x.get("raw_score", 0)), reverse=True)[:5]

        recommendations = []
        for i, item in enumerate(top5, 1):
            rec = {
                "rank": i,
                "category_name": item["category_name"],
                "category_code": item["category_code"],
                "score": item.get("score", 0),
                "per_store_sales": item["per_store_sales"],
                "store_count": item["store_count"],
                "close_rate": item["close_rate"],
                "age_match": item["age_match"],
                "monthly_sales": item["monthly_sales"],
                "reasons": item["reasons"],
            }
            if item.get("startup_cost"):
                rec["startup_cost"] = item["startup_cost"]
            recommendations.append(rec)

    message = None
    if budget and not budget_filtered:
        message = "예산 조건에 맞는 업종이 없어 전체 기준으로 추천합니다"

    result = {
        "district_code": district_code,
        "quarter": quarter,
        "recommendations": recommendations,
        "total_categories_analyzed": len(raw_scores),
    }
    if message:
        result["message"] = message

    await cache_service.set(cache_key, result, ttl=86400)
    return result
