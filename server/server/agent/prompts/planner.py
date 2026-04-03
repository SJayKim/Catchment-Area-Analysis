"""Planner prompts — intent classification & tool catalogue."""

PLANNER_CLASSIFICATION_PROMPT = """\
사용자의 질문을 분석하여 의도와 맥락을 파악하세요.

## 도구 카탈로그
| 도구 | 설명 | 파라미터 |
|------|------|----------|
| get_district_summary | 상권 종합 요약 | district_code |
| get_floating_population | 유동인구 상세 | district_code, quarter? |
| get_estimated_sales | 추정 매출 상세 | district_code, category_code? |
| get_store_info | 점포 현황 | district_code, category_code? |
| get_population_info | 상주/직장인구 | district_code |
| compare_districts | 상권 비교 (2~3개) | district_codes[] |
| recommend_business | 업종 추천 Top5 | district_code |
| get_store_history | 리스크 분석 | district_code |

## 의도 유형
summary, comparison, recommendation, risk, category_analysis, follow_up, general, ambiguous

## 대화 이력
{history}

## 현재 컨텍스트
선택 상권: {district_code} ({district_name})

## 사용자 질문
{message}

## 출력 (JSON만, 다른 텍스트 없이)
{{"intent": "...", "confidence": 0.0, "referenced_districts": ["..."], "referenced_category": null}}
"""
