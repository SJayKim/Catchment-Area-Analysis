# Quality Sweep — FAIL Details


## A-recommend-3120052  (4/7 = 57%)

- user messages: ['성수 카페말고 어떤 업종 추천?']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 성수동 상권의 데이터를 먼저 조회해서 카페 외 추천 업종을 분석해드리겠습니다.  성수동 상권을 찾아보겠습니다.  성수동 상권의 업종별 현황을 분석해보겠습니다.  **성수동은 카페 외에도 다양한 업종에서 기회가 있는 복합 상권입니다.**  ## 추천 업종 TOP 3  ### 1순위: **한식음식점**  - **월 추정 매출**: 약 42억원 `(recommend_business)` - **점포 수**: 상대적으로 적어 경쟁 부담 낮음 - **폐업률**: 4.2%로 안정적 `(recommend_business)` - **추천 이유**:
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=959 need=300
  - ✗ intent  got= need=recommendation
  - ✗ tool_names_include_any  got=[] need-any=['recommend_business', 'get_store_info', 'get_estimated_sales']
  - ✗ card_types_include_any  got=[] need-any=['recommend']

## A-risk-3120028  (4/6 = 67%)

- user messages: ['명동 창업 리스크는 뭐야?']
- intent: `recommendation`  tools: `['recommend_business']`  cards: `['recommend']`
- text preview: **명동은 높은 매출 잠재력과 함께 상당한 창업 리스크가 공존하는 상권입니다.**  ## 주요 창업 리스크  ### 1. **편의점 업종 고위험 신호** - **폐업률 25.0%** `(recommend_business)` - 이는 서울 평균(약 6-8%) 대비 3배 이상 높은 수준 - 12개 점포가 운영 중이지만 4곳 중 1곳이 문을 닫는 상황 - 높은 임대료 대비 수익성 확보 어려움 추정  ### 2. **업종별 경쟁 밀도** - 반찬가게: 15개 점포 `(recommend_business)` (밀집도 0.9%) - 안경점: 1
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=1024 need=250
  - ✗ intent  got=recommendation need=risk
  - ✗ tool_names_include_any  got=['recommend_business'] need-any=['get_store_history', 'get_store_info', 'detect_floating_pop_anomaly']

## A-sim-3120103-치킨집  (5/7 = 71%)

- user messages: ['홍대 치킨집 예상 매출?']
- intent: `category_analysis`  tools: `['get_estimated_sales', 'get_store_info']`  cards: `[]`
- text preview: **홍대 치킨집 관련 데이터가 부족하여 정확한 예상 매출을 제시할 수 없습니다.**  현재 수집된 데이터를 보면: - 홍대입구역 상권의 전체 매출 데이터가 0원으로 표시 `(get_estimated_sales)` - 치킨 전문점 관련 업종이 상위 5개 업종에 포함되지 않음 `(get_store_info)`  **대신 알 수 있는 정보:** - 홍대 상권 내 **호프-간이주점**이 246개로 3위 업종 `(get_store_info)` - 전체 점포 수는 5개로 매우 제한적인 데이터 `(get_store_info)`  **치킨집 매출
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=487 need=250
  - ✗ intent  got=category_analysis need=simulation
  - ✓ tool_names_include_any  got=['get_estimated_sales', 'get_store_info'] need-any=['estimate_revenue', 'get_estimated_sales']
  - ✗ card_types_include_any  got=[] need-any=['simulation']

## A-sim-3120052-일반음  (5/7 = 71%)

- user messages: ['성수에서 일반음식점 시뮬레이션']
- intent: `simulation`  tools: `['simulate_revenue', 'simulate_revenue', 'simulate_revenue']`  cards: `[]`
- text preview: 성수역 상권에서 일반음식점 창업 시 예상 매출을 분석해드리겠습니다.  ## 성수역 일반음식점 매출 시뮬레이션  **월 예상 매출: 약 3,850만원 `(simulate_revenue)`**  ### 📊 매출 구성 분석  **요일별 매출 패턴**: - **평일 매출**: 2,695만원 (70.0%) - 직장인 점심/저녁 수요 중심 - **주말 매출**: 1,155만원 (30.0%) - 주거지역 특성상 주말 비중 적정  **시간대별 매출 분포**: - **점심시간대 (11-14시)**: 1,540만원 (40.0%) - 최대 매출 구간 
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=909 need=250
  - ✓ intent  got=simulation need=simulation
  - ✗ tool_names_include_any  got=['simulate_revenue', 'simulate_revenue', 'simulate_revenue'] need-any=['estimate_revenue', 'get_estimated_sales']
  - ✗ card_types_include_any  got=[] need-any=['simulation']

## D-typo-2  (3/4 = 75%)

- user messages: ['홍댸 상권 어뗘?']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 안녕하세요! 홍대 상권 분석을 도와드리겠습니다.  홍대 상권이라고 하시면 **홍익대학교 주변 상권**을 말씀하시는 것 같은데, 정확한 분석을 위해 구체적인 상권명을 확인해주세요.  서울시 공식 상권 분류에서 홍대 지역 관련 상권들: - **홍대입구역** 상권 - **홍익대학교** 상권   - **상수역** 상권 - **합정역** 상권  어떤 상권을 분석해드릴까요? 상권명을 정확히 알려주시면 유동인구, 매출, 업종 현황 등을 상세히 분석해드리겠습니다! 🎯
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✗ card_district_name_any  got=[] need-any=['홍대입구역(홍대)']

## E-coref-동일  (3/4 = 75%)

- user messages: ['건대 요약', '동일 상권의 카페 현황?']
- intent: `category_analysis`  tools: `['get_estimated_sales', 'get_store_info', 'get_estimated_sales', 'get_store_info', 'get_estimated_sales', 'get_store_info']`  cards: `[]`
- text preview: **건대입구역 카페 현황을 분석해드리겠습니다.**  ## 카페(커피-음료) 현황  **점포 수**: 총 88개 `(get_store_info)`로 전체 업종 중 **4위**를 차지합니다. 한식음식점(156개), 호프-간이주점(126개)에 이어 상당한 규모를 형성하고 있습니다.  **창업/폐업 동향**: 이번 분기 신규 개업 3개, 폐업 6개로 **순감소 3개**를 기록했습니다. 폐업이 개업보다 많아 카페 시장이 다소 위축되는 모습입니다.  **시장 특성**: 건대 전체 프랜차이즈 비율이 35.3%인 점을 고려할 때, 카페 업종도 스
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✗ coref_resolved_to  need=건대입구역(건대) names=[]

## E-coref-그 업종  (3/4 = 75%)

- user messages: ['홍대 카페 매출 어때?', '그 업종 다른 상권에선 어떨까?']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 비교 분석을 위해서는 최소 2개 상권이 필요합니다. 두 상권을 모두 알려주시겠어요? (예: '강남역이랑 홍대입구역 매출 비교')
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✗ min_text_chars  got=71 need=150

## G-switch-district  (3/4 = 75%)

- user messages: ['강남역 요약', '아니 건대 요약으로 해줘']
- intent: `summary`  tools: `['get_district_summary']`  cards: `['summary']`
- text preview: **건대입구는 대학가 특성이 강한 발달상권으로, 젊은 층 중심의 활발한 소비가 이루어지는 상권입니다.**  ## 📊 핵심 지표 분석  **유동인구**: 하루 평균 22만 8천명 `(get_district_summary)`으로, 서울 평균(9만 2천명) 대비 **2.5배** 높은 수준입니다. 오후 6시(5만 1천명)에 피크를 기록하며, 20대가 31.2%로 가장 높은 비중을 차지하는 전형적인 **대학가 상권**입니다.  **매출 규모**: 월 추정 매출 346억 8천만원 `(get_district_summary)`으로 상당한 규모를 
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✗ card_district_name  got=['강남역'] need=건대입구역(건대)

## G-switch-then-back  (3/4 = 75%)

- user messages: ['강남역 요약', '잠깐 홍대는?', '다시 강남 추천 업종']
- intent: `recommendation`  tools: `['recommend_business']`  cards: `['recommend']`
- text preview: # 강남역 추천 업종 분석  **강남역에서는 편의점이 압도적 1순위 추천이지만, 높은 폐업률 리스크를 반드시 고려해야 합니다.**  ## 🏆 상위 5개 업종 비교 (2025Q4 기준)  ### 1위: 편의점 (점수 100.0) - **점포당 월매출**: 3억 6,115만원 `(recommend_business)` - 압도적 수익성 - **경쟁 현황**: 17개 점포 (밀집도 0.3%) - 경쟁 여유 - **고객 매칭**: 73% - 20~30대 직장인층과 완벽 매칭 - **⚠️ 리스크**: 폐업률 29.4% (고위험) - 3곳 중 
  - ✓ done_event  
  - ✓ trace_id  
  - ✓ no_xml_leak  
  - ✗ card_district_name_any  got=[] need-any=['강남역']

## I-greeting  (3/4 = 75%)

- user messages: ['안녕']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 안녕하세요! 서울 상권 분석 AI 마켓스코프입니다. 지도에서 상권을 선택하시거나, 분석할 상권명을 알려주세요!
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=61 need=30