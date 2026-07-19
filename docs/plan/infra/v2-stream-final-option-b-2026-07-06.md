# v2 final 스트리밍 옵션 B — astream 버퍼링 + 진행 이벤트 세분화 (Trust 의미론 무변경)

> 작성: 2026-07-06 · 선행: deferred-backlog-2026-07-04.md (git history) Item 3 (옵션 B 권고 + 착수 게이트)

## Context

- v2 루프는 최종 LLM 응답을 `ainvoke` 로 통으로 받고 Trust Kernel 검증 후 `_chunks(90)` 로 방출(`engine.py`) — 마지막 tool_end 이후 최대 수십 초 무음. 진짜 토큰 스트리밍은 "검증-후-방출" 설계와 정면 충돌.
- **옵션 B**: final 호출을 `astream` 으로 받되 **버퍼링**, 수신 중 `"응답 작성 중... n%"` 진행 이벤트 세분화, 검증 후 **일괄 방출**. Trust 의미론 무변경 — 지각 개선만.
- 착수 게이트 3조건(백로그 Item 3): (1) e2e 스택 + live LLM 키 (2) S1~S8 재실행 평균 ≥9.0 & 날조 0 (R4 기준) (3) SSE staleness/in-flight 가드와 이벤트 순서 호환.
- **Memory 참조**: `feedback_streaming_diagnose_ttft`(긴 LLM 대기 구간엔 progress emit — 직접 근거) · `feedback_marketscope_sse_format`(data: JSON 임베드 관례 유지) · `feedback_compose_env_block_overrides_env_file`(e2e USE_MOCK 호스트 export) · `feedback_formatter_strips_unused_imports`(구현 중 재확인). 백로그가 참조한 `feedback_sse_done_staleness`/`feedback_chat_inflight_guard` 는 memory 파일 미실존 — 실체는 코드(`eventHandlers.ts:51-62` requestId 가드, `chatStore.ts` in-flight abort)로 대체 참조.

## Scope

- **In**: `models.py` `astream_with_fallback`+`_chunk_text` 신설 / `engine.py` 메인 턴 분기 / `config.py` 4필드 / `eventHandlers.ts` thinking 라벨 갱신 / 테스트 2파일 신설 + stale 1파일 정리 / eval 재판정 → prod
- **Out**: 교정 패스 스트리밍(드묾·이득 없음), 옵션 A(문장 단위 검증 — 글로벌 교정 패스 상실), 옵션 C(patch 이벤트 프로토콜), 타임아웃 partial 채택(의미론 변경 — follow-up), chat.py/sseParser/PAE 경로

## Design

| 결정 | 내용 | 근거 |
|---|---|---|
| 인터페이스 | `astream_with_fallback` = **async generator** — `{"kind":"delta","chars","tool_call"}` × n → `{"kind":"final","message"}` 1회 | engine 자체가 generator 라 `async for` 자연 합성. 콜백이면 큐+task 배관(누수·순서 비결정) 필요 |
| 폴백 | 첫 청크 전/mid-stream 실패 모두 **버퍼 폐기 후 다음 후보 재시작** | 버퍼링이라 사용자 미노출 — 폐기 비용 0. breaker 위상은 ainvoke parity |
| timeout | `asyncio.timeout` 컨텍스트 (generator 라 wait_for 불가, respond.py 패턴). TimeoutError = 후보 실패 | parity 유지, partial 채택은 follow-up |
| abort | `except Exception` 은 CancelledError/GeneratorExit(BaseException) 미포착 → breaker 무기록 | 테스트로 고정 |
| 최종 조립 | `AIMessageChunk` `+` 누적 → `message_chunk_to_message` (tool_call_chunks→tool_calls 정규화) | ainvoke 결과와 동일하게 히스토리 직렬화 |
| 진행 이벤트 | 기존 `{"type":"thinking","step"}` 재사용 (신규 타입 없음) | chat.py/sseParser/types.ts/staleness 가드 무접촉 |
| 억제 가드 | ① tool_call 청크 등장 즉시 ② `chars < 120`(min) ③ 80자 간격 스로틀 ④ pct 단조 clamp(`best_pct`) | 도구 턴 서두 오인 방지 + mid-stream 재시작 % 역행 방지 |
| 진행률 | `min(99, chars*100 // 1100)` — "살아있고 진전 중" 신호가 목적 | 정확한 % 아님, 99% 캡 |
| 적용 지점 | 메인 루프 턴만. 교정 패스(ainvoke)·Trust 게이트·`_chunks` 방출 무변경 | 검증-후-방출 불변식 보존 |
| 롤백 | `AGENT_LOOP_STREAM_FINAL=false` env — 코드 배포 없이 기존 경로 복원 | prod 1차 롤백 스위치 |

config 신규: `agent_loop_stream_final=True` / `agent_loop_progress_min_chars=120` / `agent_loop_progress_interval_chars=80` / `agent_loop_expected_answer_chars=1100`

## Checklist

- [x] C1 `models.py`: `astream_with_fallback` + `_chunk_text` (ainvoke 무수정)
- [x] C2 `config.py`: 스트리밍 4필드
- [x] C3 `engine.py`: 메인 턴 분기 + 진행 이벤트 (스로틀·tool 억제·monotonic %) — Trust 게이트 이하 무변경
- [x] C4 `eventHandlers.ts`: response step 라벨 갱신 (`in_progress` 가드)
- [x] C5 테스트: `test_loop_models_stream.py` 8건 + `test_engine_stream_events.py` 5건 (전건 PASS)
- [x] C6 stale `test_trust_redaction.py`: 미중복 4케이스 `test_trust_kernel_regressions.py` 이식(23 passed) 후 삭제
- [x] V1 server pytest 전체 + ruff — **205 passed / 8 skip**, 수집 에러 0
- [x] V2 frontend `tsc --noEmit` 0 error
- [x] V3 e2e 스택 (:8002, USE_MOCK=false printenv 확인, anthropic live 키) — 신규 코드 docker cp + grep 검증
- [x] V4 SSE 타임라인: 진행 11건 % 단조·text 일괄·done 정상. **발견: 분모 1100 → 99% 정체 12.5s → 2400 상향** (실측 답변 ~2,000자)
- [x] V5 Accuracy Eval — **GATE PASS 4/4** (평균 10.0 / 날조 0 / 절단 0/9 / S7 10.0). [Verdict](../../qa/runs/eval-stream-b-2026-07-06/_verdict.md)
- [x] V6 usage probe PASS — streaming 최종 메시지 `usage_metadata` 정상 (컨테이너 내 실호출)
- [ ] V7 main 머지+push `dc11186` ✅ · CI 5/5 green ✅ · **서버측 auto_deploy 미발화 (timer disabled/blocked 추정)** — 서버에서 `bash scripts/deploy/auto_deploy.sh --force` 또는 timer enable 필요. 발화 후 prod SSE 에 "응답 작성 중 n%" 확인

## 재검토 (Self-Review Gate)

- [x] 엣지: mid-stream 폴백 % 역행 → `best_pct` 단조 clamp (테스트 고정)
- [x] 엣지: Gemini 단일 청크 완결 tool_call 조립 (테스트 고정) — e2e 에서 Gemini 강제 폴백 스팟 체크 1회 권장. 불안정 시 컨틴전시: gemini 후보만 내부 ainvoke (인터페이스 불변)
- [x] 엣지: 프론트 abort → CancelledError breaker 무기록 (aclose 테스트 고정)
- [x] Memory: SSE data:JSON 관례·streaming TTFT progress·compose env 함정 반영
- [x] 충돌: trust-fallback-redaction-2026-07-03 산출물(trust.py) 무접촉 — Trust 함수 시그니처 무변경
- [x] 가드 호환: 진행 이벤트가 기존 thinking 타입 → requestId staleness 가드 자동 적용, 첫 text 에서 step completed 회수 경로 불변
- [ ] heartbeat(ping comment 프레임)와 data 프레임 충돌 없음 — V4 에서 실측
- ⚠ **auto_deploy 주의**: main push + CI green = 2분 폴링 자동배포 → **eval GATE PASS 전 main 머지 금지** (feature 브랜치 `feat/stream-final-option-b` 에서 검증)

## Scenario (E2E Ring Mapping)

| ID | Ring | 내용 | 기대 |
|---|---|---|---|
| `R1-F02-STREAMPROGRESS-01` | Ring 1 (F02) | live 스택 `/api/chat` 분석 질의 SSE 캡처 | `응답 작성 중... n%` ≥1건 · % 단조 · text 는 진행 종료 후 일괄 · done 절단 0 |
| `R1-F02-STREAMPROGRESS-02` | Ring 1 | 도구 다회 호출 질의 (비교/추천) | 도구 턴 중 진행 이벤트 0건 (tool/tool_end 사이 미방출) |
| `R3-F02-STREAMTOGGLE-01` | Ring 3 | `AGENT_LOOP_STREAM_FINAL=false` 재기동 | 진행 이벤트 0건 + 기존 응답 계약 유지 (롤백 경로 실증) |

> 사전조건: live LLM 키 e2e 스택 (:8002, USE_MOCK=false) — mock 은 PAE 폴백이라 본 경로 미경유. 단위/통합 레벨은 pytest 13건이 커버.

## Pass 반복

- **Pass 1 (기본)**: C1~C6 + 신규 pytest 13건 green ✅
- **Pass 2 (엣지)**: 폴백 재시작·도구 턴 억제·토글 off·abort breaker 무기록 — 단위 테스트로 코드화 ✅ / e2e Gemini 폴백 스팟 체크는 V3~V4 에 포함
- **Pass 3 (성능/실측)**: V4 타임라인 (무음 구간 수십 초 → 수 초) + V5 eval GATE + V6 Langfuse cost

## Agent 모델 선택

- 설계: opus 급 (완료 — 본 문서 + 세션 plan)
- 구현: sonnet 급 (스펙 확정 상태 — 본 세션에서 수행)
- 검증: pytest/ruff/tsc 는 exit code 판정, eval 채점만 상위 모델/사람 판단

## Validation

| 단계 | 명령/방법 | 기준 |
|---|---|---|
| V1 | `cd server && ruff check . && python -m pytest` | all pass, 수집 에러 0 |
| V2 | `cd frontend && npx tsc --noEmit` | 0 error |
| V3 | `USE_MOCK=false` export 후 e2e 스택 up (:8002) | `/api/chat` 200, v2 경로 확인 |
| V4 | `curl -sN :8002/api/chat` 타임스탬프 캡처 | 최대 무음 구간 ≤ 수 초, % 단조, text 일괄 |
| V5 | `BASE=http://localhost:8002 OUT=docs/qa/runs/eval-stream-b-2026-07-06 bash scripts/eval/run_accuracy_round2.sh` → `parse_sse.py` → verdict | 평균 ≥9.0 / 날조 0 / 절단 0 / S7 ≥9.3 |
| V6 | Langfuse trace 의 generation usage/cost | non-null (stream_usage 최종 청크) |
| V7 | main 머지 → `auto_deploy.sh` 폴링 관찰 → prod SSE smoke 1건 | smoke pass. 롤백 1차 = env 토글, 2차 = auto_deploy prev 이미지 |

## Metadata

- 브랜치: `feat/stream-final-option-b` (eval PASS 전 main 금지)
- 변경 파일: `server/server/agent/loop/models.py` · `server/server/agent/loop/engine.py` · `server/server/config.py` · `frontend/src/lib/eventHandlers.ts` · `server/tests/test_loop_models_stream.py`(신규) · `server/tests/test_engine_stream_events.py`(신규) · `server/tests/test_trust_kernel_regressions.py`(+4 이식) · `server/tests/test_trust_redaction.py`(삭제)
- Deferred(follow-up): 타임아웃 partial 채택(answer-shaped 시 truncated 플래그) · 교정 패스 스트리밍 · PAE 경로 진행 이벤트
