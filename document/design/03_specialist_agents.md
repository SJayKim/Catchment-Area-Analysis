# Phase 1: Specialist Agents Checklist

## Agent 1: Population (인구분석)
- [ ] `app/agents/population.py`
- [ ] MCP 도구 호출 (유동인구, 거주인구, 직장인구)
- [ ] 시간대/요일별 분석 로직
- [ ] PopulationAnalysis 출력

## Agent 2: Revenue (매출분석)
- [ ] `app/agents/revenue.py`
- [ ] MCP 도구 호출 (상권 매출, 업종별 매출)
- [ ] 매출 추정 로직 (population 의존)
- [ ] RevenueAnalysis 출력

## Agent 3: Competition (경쟁분석)
- [ ] `app/agents/competition.py`
- [ ] MCP 도구 호출 (업종 점포수, 개폐업)
- [ ] 시장 포화도 산출
- [ ] CompetitionAnalysis 출력

## Agent 4: Location (입지분석)
- [ ] `app/agents/location.py`
- [ ] MCP 도구 호출 (지하철, 버스, 주변시설)
- [ ] 접근성/가시성 점수 산출
- [ ] LocationAnalysis 출력
