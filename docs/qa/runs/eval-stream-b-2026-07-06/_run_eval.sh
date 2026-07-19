#!/bin/bash
# Accuracy Eval — 옵션 B 스트리밍 재판정 (S1~S8, R4 방법론: message-only + --max-time 180).
# 원본: scripts/eval/run_accuracy_round2.sh (max-time 만 90→180, R4 관례).
set -euo pipefail

BASE="${BASE:-http://localhost:8002}"
SESSION_PREFIX="eval-stream-b-$(date +%s)"
OUT="${OUT:-docs/qa/runs/eval-stream-b-2026-07-06}"
mkdir -p "$OUT"

echo "BASE=$BASE  OUT=$OUT  SESSION=$SESSION_PREFIX"
date +%s > "$OUT/_session_ts.txt"

send() {
  local id=$1 msg=$2 session=$3
  local payload
  payload=$(python -c "import json,sys; print(json.dumps({'message':sys.argv[1],'session_id':sys.argv[2]}))" "$msg" "$session")
  echo ">>> $id session=$session msg=\"$msg\""
  curl -sN --max-time 180 -X POST "$BASE/api/chat" \
    -H "Content-Type: application/json" -H "Accept: text/event-stream" \
    -d "$payload" > "$OUT/$id.sse" || echo "!!! $id curl exit=$?"
  local bytes=$(wc -c < "$OUT/$id.sse")
  echo "<<< $id bytes=$bytes"
}

send S1 "강남역 상권 요약해줘"           "${SESSION_PREFIX}-s1"  # GT 3120189
send S2 "서울역 상권 분석"               "${SESSION_PREFIX}-s2"  # GT 3120043
send S3 "홍대 vs 성수 매출 비교"         "${SESSION_PREFIX}-s3"
send S4 "건대 창업 추천 업종?"           "${SESSION_PREFIX}-s4"  # GT 3120053
send S5 "명동 창업 리스크는?"            "${SESSION_PREFIX}-s5"  # GT 3120028
send S6 "강남역에서 카페 차리면 매출 얼마?" "${SESSION_PREFIX}-s6"  # GT 3120189
send S7-pre "홍대 vs 성수 매출 비교" "${SESSION_PREFIX}-s7"
sleep 1
send S7 "거기 중에 유동인구 더 많은 곳?" "${SESSION_PREFIX}-s7"
send S8 "홍대 말고 성수역이랑 건대 비교" "${SESSION_PREFIX}-s8"

echo "done."
