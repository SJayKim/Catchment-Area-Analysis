#!/bin/bash
# Accuracy Round 2 eval — S1~S8 SSE capture.
#
# Usage:
#   BASE=http://localhost:8000 bash scripts/eval/run_accuracy_round2.sh
#
# 2026-04-27 변경 (P0-4): district_code 하드코딩 제거.
#   - 기본은 message-only payload → planner entity_linking 자체를 검증.
#   - tool 동작 smoke 가 필요하면 `WITH_CODES=1` 로 ground-truth 코드 동봉.
#   - 과거에 S2(서울역=3110023 = 서울대병원)·S5(명동=3110010 = 평창동서측) 처럼
#     오매핑된 코드를 보내는 바람에 시스템 회귀로 오독되던 문제를 차단.
#   참조: docs/qa/analysis-quality-eval-2026-04-24.md §4.1
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
SESSION_PREFIX="eval-r2-$(date +%s)"
OUT="${OUT:-docs/qa/runs/eval-round2-raw}"
WITH_CODES="${WITH_CODES:-0}"
mkdir -p "$OUT"

echo "BASE=$BASE  OUT=$OUT  SESSION=$SESSION_PREFIX  WITH_CODES=$WITH_CODES"

send() {
  local id=$1 msg=$2 session=$3 code=${4:-}
  local payload
  if [[ "$WITH_CODES" == "1" && -n "$code" ]]; then
    payload=$(python3 -c "import json,sys; print(json.dumps({'message':sys.argv[1],'session_id':sys.argv[2],'district_code':sys.argv[3]}))" "$msg" "$session" "$code")
  else
    payload=$(python3 -c "import json,sys; print(json.dumps({'message':sys.argv[1],'session_id':sys.argv[2]}))" "$msg" "$session")
  fi
  echo ">>> $id session=$session msg=\"$msg\""
  curl -sN --max-time 90 -X POST "$BASE/api/chat" \
    -H "Content-Type: application/json" -H "Accept: text/event-stream" \
    -d "$payload" > "$OUT/$id.sse" || echo "!!! $id curl exit=$?"
  local bytes=$(wc -c < "$OUT/$id.sse")
  echo "<<< $id bytes=$bytes"
}

# Codes are kept as ground-truth comments; only forwarded when WITH_CODES=1.
send S1 "강남역 상권 요약해줘"           "${SESSION_PREFIX}-s1" 3120189  # 강남역(강남) 발달
send S2 "서울역 상권 분석"               "${SESSION_PREFIX}-s2" 3120043  # 서울역 발달
send S3 "홍대 vs 성수 매출 비교"         "${SESSION_PREFIX}-s3"
send S4 "건대 창업 추천 업종?"           "${SESSION_PREFIX}-s4" 3120053  # 건대입구역(건대) 발달
send S5 "명동 창업 리스크는?"            "${SESSION_PREFIX}-s5" 3120028  # 명동(명동거리) 발달
send S6 "강남역에서 카페 차리면 매출 얼마?" "${SESSION_PREFIX}-s6" 3120189  # 강남역(강남) 발달

# S7: session shared with preceding comparison for coreference test
send S7-pre "홍대 vs 성수 매출 비교" "${SESSION_PREFIX}-s7"
sleep 1
send S7 "거기 중에 유동인구 더 많은 곳?" "${SESSION_PREFIX}-s7"

send S8 "홍대 말고 성수역이랑 건대 비교" "${SESSION_PREFIX}-s8"

echo "done."
