# ADR — Langfuse 호스팅 선택 (LLMOps L1)

> **Status**: Accepted
> **Date**: 2026-04-21
> **Scope**: LLMOps L1 (Trace 활성화) — `docs/plan/infra/llmops-platform.md` §3.3.1

## Context

LLM/Agent 실행 trace 수집을 위해 Langfuse 를 도입한다. 호스팅 방식 3종 비교:

| 옵션 | 연동 비용 | 운영 부담 | 데이터 주권 | 스택 추가 |
|------|-----------|-----------|-------------|-----------|
| **Langfuse Cloud** | 15분 이내 | 없음 | 외부 SaaS | 0 |
| **Self-host v2** | 1~2 일 | Postgres 1개 운영 | ✅ | Postgres only |
| **Self-host v3** | 3~5 일 | Postgres + ClickHouse + Redis + MinIO | ✅ | 4종 스택 |

## Decision

**Langfuse Cloud** 를 L1 단계에서 채택한다.

### 근거

1. **최소 연동 비용** — `server/pyproject.toml` 에 `langfuse>=2.0` 이미 있고, `config.py` 에 env 3개 (`public_key`, `secret_key`, `host`) 슬롯이 준비됨. 코드 변경 범위가 graph.py handler 주입 + session 해시 유틸로 국한.
2. **데이터 부담 제한적** — 현재 서비스는 상권 코드/질의 텍스트만 trace 에 실리며 **PII 는 session_id 해시 + message 원본**만. 결제/인증 도입 전까지 외부 SaaS 리스크 < 자체 운영 리스크.
3. **v3 self-host 배제** — ClickHouse + MinIO 추가는 현 `docker-compose.yml` (db + redis + backend + frontend + nginx) 대비 스택 2배 증가. 운영 가치 대비 과투자.
4. **v2 self-host 보류** — Postgres 1개로 끝나지만, 스키마 업그레이드 자체 관리 + Langfuse v3 마이그레이션 리스크. L4 에서 PII 요구가 명확해질 때 재평가.

## Consequences

### 긍정
- L1 구현을 1~2 일 내 완료 가능 (plan KPI `기간 1~2주` 대비 여유).
- Langfuse Cloud 의 Slack webhook, dataset UI, score UI 를 L3/L4 에서 즉시 활용 가능 (self-host 는 UI 피처가 지연 반영).
- 장애 시 graceful degrade (`_anthropic_valid` 패턴 재사용) 로 서비스 영향 없음.

### 부정 및 완화
- **외부 SaaS 의존** — Langfuse Cloud 다운 시 trace 손실. 서비스 `/api/chat` 는 영향 없음 (best-effort handler). 주요 데이터는 Langfuse dataset → JSON export 주기적 백업으로 완화.
- **요금** — 현재 트래픽 수준(개발/데모)에서 Free tier 범위. 프로덕션 부하 증가 시 비용 계측 필요. L4 Cost 계획에 포함.
- **PII 정책** — session_id 는 `hashlib.sha256(salt + session_id)` 해시만 저장. 원본 session_id, user email, IP 는 Langfuse trace 에 금지 (코드 리뷰 시 `_hash_session()` 경유 강제).

## SDK Version Pin

Langfuse Python SDK 는 **`>=2.0,<3.0`** 으로 고정한다.

- v3/v4 는 `langchain` 풀패키지 의존성 (`langfuse.langchain.CallbackHandler` 가 `import langchain` 강제).
- 현 스택은 `langchain-core` + provider 패키지만 사용 (경량). 풀패키지 추가 시 배포 이미지 증가 + 불필요한 의존성.
- v2 `langfuse.callback.CallbackHandler` API 는 본 plan §3.3.1 의사코드와 일치.
- L5 에서 실험적 기능이 필요해지면 v3 전환 ADR 별도 작성.

## Migration Path (L4+)

결제/구독 도입으로 사용자별 conversation 이 PII 대상이 되는 시점에:
1. Langfuse Cloud → v2 self-host 마이그레이션 (Postgres 단일, 기존 dataset 은 API export/import).
2. Public/Secret key 로테이션 + compose 스택 재기동.
3. 본 ADR 을 `Superseded` 로 마킹하고 새 ADR 작성.

## References

- `docs/plan/infra/llmops-platform.md` §3.3.1 Observability (Hosting 선택 표)
- `server/pyproject.toml:27` — `langfuse>=2.0`
- `server/server/config.py:39-42` — Langfuse env 3 slot
- `server/server/agent/graph.py` — CallbackHandler 주입 타깃
