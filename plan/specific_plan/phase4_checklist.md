# Phase 4 리팩토링 & 문서 보강 체크리스트

> 최종 업데이트: 2026-03-21
> 상태: ✅ 구현 완료

---

## Part 1: 코드 재구성

### Step 1: user_input_node 추가
- [x] `graph/nodes.py` — `user_input_node()` 함수 작성
- [x] `graph/workflow.py` — 엔트리포인트 `user_input` 변경, `user_input → commander_plan` 엣지
- [x] import 검증

### Step 2: debate_check_node 추가
- [x] `graph/nodes.py` — `debate_check_node()` 함수 작성
- [x] `graph/edges.py` — `route_after_debate_check()` 추가, `should_run_debate()` 제거(로직 이전 완료)
- [x] `graph/workflow.py` — `risk → debate_check → conditional(debate|judgment)` 재연결
- [x] `models/state.py` — `debate_decision`, `debate_trigger_reasons` 필드 추가
- [x] import 검증

### Step 3: 워크플로우 통합 검증
- [x] `python -c "from app.graph.workflow import build_workflow; build_workflow()"` 성공 확인
- [x] 전체 노드 수 20개 확인 (기존 18 + user_input + debate_check)

### Step 4: Finance MCP 서버
- [x] `app/mcp_servers/finance/__init__.py`
- [x] `app/mcp_servers/finance/server.py`
- [x] `app/mcp_servers/finance/tools.py` (6개 도구)
- [x] `app/mcp_servers/finance/schemas.py`
- [x] `app/mcp_servers/finance/api_client.py`
- [x] MCPClientRouter 등록 (config.py에 port 5105)

### Step 5: Database MCP 서버
- [x] `app/mcp_servers/database/__init__.py`
- [x] `app/mcp_servers/database/server.py`
- [x] `app/mcp_servers/database/tools.py` (5개 도구)
- [x] `app/mcp_servers/database/schemas.py`
- [x] `app/mcp_servers/database/db_client.py`
- [x] MCPClientRouter 등록 (config.py에 port 5106)

### Step 6: Google Maps MCP 서버
- [x] `app/mcp_servers/google_maps/__init__.py`
- [x] `app/mcp_servers/google_maps/server.py`
- [x] `app/mcp_servers/google_maps/tools.py` (5개 도구)
- [x] `app/mcp_servers/google_maps/schemas.py`
- [x] `app/mcp_servers/google_maps/api_client.py`
- [x] MCPClientRouter 등록 (config.py에 port 5107)

### Step 7: Naver Maps MCP 서버
- [x] `app/mcp_servers/naver_maps/__init__.py`
- [x] `app/mcp_servers/naver_maps/server.py`
- [x] `app/mcp_servers/naver_maps/tools.py` (5개 도구)
- [x] `app/mcp_servers/naver_maps/schemas.py`
- [x] `app/mcp_servers/naver_maps/api_client.py`
- [x] MCPClientRouter 등록 (config.py에 port 5108)

### Step 8: MCP 통합 검증
- [x] MCPClientRouter 전체 서버 9개 등록 확인
- [x] docker-compose.yml 신규 서비스 4개 반영
- [x] import 검증 (finance=6, database=5, google=5, naver=5 도구)

---

## Part 2: MCP 서버 문서

### Step 9: MCP 스펙 문서 3건
- [x] `document/specs/05_mcp_servers_database.md`
- [x] `document/specs/05_mcp_servers_google_maps.md`
- [x] `document/specs/05_mcp_servers_naver_maps.md`

---

## Part 3: 누락 문서 작성

### Step 10: 배포 & 인프라
- [x] `document/specs/11_deployment.md`

### Step 11: 테스트 전략
- [x] `document/specs/12_testing.md`

### Step 12: CI/CD
- [x] `document/specs/13_cicd.md`

### Step 13: 보안
- [x] `document/specs/14_security.md`

### Step 14: 운영 & 트러블슈팅
- [x] `document/specs/15_operations.md`

### Step 15: Grafana 대시보드
- [x] `monitoring/grafana/dashboards/marketscope_overview.json`

### Step 16: 성능 벤치마크
- [x] `document/specs/16_performance.md`

### Step 17: 개발자 온보딩
- [x] `document/specs/17_developer_guide.md`

### Step 18: 최종 검증
- [x] 전체 import 검증 ✅
- [x] 워크플로우 빌드 검증 ✅ (20 nodes)
- [x] 문서 목록 크로스체크 ✅ (11개 신규 파일)

---

## 검증 결과 (2026-03-21)

```
✅ Workflow: 20 nodes (user_input, debate_check 추가)
✅ MCP Servers: 9개 (기존 5 + finance, database, google_maps, naver_maps)
✅ MCP Tools: finance=6, database=5, google_maps=5, naver_maps=5
✅ State: debate_decision, debate_trigger_reasons 필드 추가
✅ Edge: route_after_debate_check (should_run_debate 대체)
✅ Docker: docker-compose.yml에 4개 MCP 서비스 추가
✅ Grafana: marketscope_overview.json 대시보드 (12 패널)
✅ Documents: 11개 신규 스펙 문서 작성
```
