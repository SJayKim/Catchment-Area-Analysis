# Quality Sweep — FAIL Details


## UJ1-pub-건대  (3/6 = 50%)

- user messages: ['건대입구 유동인구 얼마나 돼?', '저녁 피크 시간대 언제야?', '주점 몇 개 있어?', '이 상권에서 가장 안전한 창업 업종 추천해줘']
- intent: `risk`  tools: `['get_store_history']`  cards: `['risk']`
- text preview: 건대입구역에서 **가장 안전한 창업 업종은 한식음식점**입니다. 폐업률이 낮고 시장 규모가 충분해 안정적인 사업이 가능합니다.  ## 안전 업종 순위 (폐업률 기준)  **1순위: 한식음식점** - **폐업률**: 3.2% `(get_store_history)` - 서울 평균(5.9%) 대비 절반 수준 - **시장 규모**: 156개로 최대 업종, 충분한 고객 수요 확보 - **안정성**: 대학가 필수 업종으로 지속적 수요  **2순위: 호프-간이주점**  - **폐업률**: 3.2% `(get_store_history)` - **
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=853 need=150
  - ✗ intent_any  got=risk need-any=['recommendation']
  - ✗ tool_names_include_any  got=['get_store_history'] need-any=['recommend_business']

## UJ2-switch-강남-종로  (5/7 = 71%)

- user messages: ['강남역 상권 요약', '종로3가역은 어때?', '둘 중에 월 매출 더 높은 곳 어디야?', '아까 강남 얘기로 돌아가서 추천 업종 알려줘']
- intent: `recommendation`  tools: `['recommend_business']`  cards: `['recommend']`
- text preview: **강남역에서는 편의점이 1순위 추천 업종입니다. 점포당 월 3억 6천만원의 압도적 매출을 기록하고 있습니다.**  ## 🏆 상위 5개 업종 비교  ### 1위: 편의점 (점수 100.0) - **점포당 월매출**: 3억 6,115만원 `(recommend_business)` - 압도적 1위 - **경쟁 현황**: 17개 점포 (밀집도 0.3%)로 **포화도 여유** - **고객 매칭**: 73% - 강남역 고객층과 잘 맞음 - **⚠️ 리스크**: 폐업률 29.4%로 **고위험** 수준  ### 2위: 서적 (점수 29.3) - 
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=928 need=150
  - ✓ intent_any  got=recommendation need-any=['recommendation']
  - ✗ card_district_name_any  got=[] need-any=['강남역']
  - ✓ coref_resolved_to  need=강남 names=[]

## UJ2-switch-홍대-성수  (2/6 = 33%)

- user messages: ['홍대 상권 요약', '성수역도 보여줘', '이 두 곳 비교해줘']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 비교 분석을 위해서는 최소 2개 상권이 필요합니다. 두 상권을 모두 알려주시겠어요? (예: '강남역이랑 홍대입구역 매출 비교')
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✗ intent_any  got= need-any=['comparison']
  - ✗ tool_names_include  missing=['compare_districts'] got=[]
  - ✗ compare_district_count_min  got=0 need≥2

## UJ2-switch-명동-남대문  (3/4 = 75%)

- user messages: ['명동 상권 분석해줘', '남대문시장은 어때?', '관광지 특성은 어느 쪽이 더 강해?']
- intent: `comparison`  tools: `['compare_districts']`  cards: `['compare']`
- text preview: **관광지 특성은 명동이 압도적으로 강합니다.**  ## 🏛️ 관광지 특성 비교  **명동**은 전형적인 **국제 관광 상권**입니다: - 하루 **200만명** `(compare_districts)` 이라는 압도적 유동인구는 국내외 관광객이 주축 - **20대 중심** `(compare_districts)` 고객층으로 젊은 관광객과 쇼핑객이 몰림 - 오후 2시 피크의 **낮시간 집중형** 패턴은 관광 일정에 맞춘 방문 특성 - 점포당 월 **2,477만원** `(compare_districts)` 의 높은 매출 효율은 관광객의 높
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=761 need=150

## UJ2-switch-잠실-신촌  (2/4 = 50%)

- user messages: ['잠실역 상권 요약해줘', '신촌은 어때?', '대학가 상권이랑 번화가 상권 차이점 알려줘']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 비교 분석을 위해서는 최소 2개 상권이 필요합니다. 두 상권을 모두 알려주시겠어요? (예: '강남역이랑 홍대입구역 매출 비교')
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✗ min_text_chars  got=71 need=200

## UJ4-report-from-compare  (2/4 = 50%)

- user messages: ['홍대랑 성수역 비교해줘', '홍대에 어떤 업종 추천해?', '이 비교+추천 내용 상세 리포트 PDF로 저장']
- intent: `None`  tools: `[]`  cards: `[]`
- text preview: 비교 분석을 위해서는 최소 2개 상권이 필요합니다. 두 상권을 모두 알려주시겠어요? (예: '강남역이랑 홍대입구역 매출 비교')
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✗ pdf_trigger  

## UJ4-long-synthesis  (4/6 = 67%)

- user messages: ['이태원 관광특구 상권을 상세 분석 보고서 형태로 정리해줘. 유동인구, 월 매출, 점포 수, 추천 업종, 리스크 모두 포함해서 길게 써줘']
- intent: `risk`  tools: `['get_store_history']`  cards: `['risk']`
- text preview: 이태원 관광특구 상권에 대한 상세 분석을 위해 추가 데이터를 수집하겠습니다.  # 이태원 관광특구 상권 종합 분석 보고서  ## 📊 Executive Summary  **이태원은 외국인 관광객과 다문화 특성이 강한 서울의 대표적인 관광특구 상권으로, 독특한 문화적 정체성을 바탕으로 한 특화된 상업 생태계를 형성하고 있습니다.**  현재 1,389개 점포가 운영 중이며 `(get_store_history)`, 최근 분기 기준 신규 개점 38개, 폐점 36개로 순증가 2개를 기록하여 안정적인 상권 활력을 보이고 있습니다. 다만 일부 업
  - ✓ done_event  
  - ✗ trace_id  
  - ✓ no_xml_leak  
  - ✓ min_text_chars  got=2158 need=500
  - ✗ tool_names_include_any  got=['get_store_history'] need-any=['get_district_summary', 'get_floating_population', 'get_estimated_sales']
  - ✓ must_contain_any_in_text  need-any=['유동인구', '매출', '점포']