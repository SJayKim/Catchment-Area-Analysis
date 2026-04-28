#!/usr/bin/env bash
# Backend direct smoke for planner 2026-04-24 changes.
# - clarification short-circuit (ambiguous)
# - comparison multi-district + map_cmd
# - rewriter exclusion
set -u
B=${B:-http://localhost:8000}

post() {
  local sid="$1" msg="$2"
  curl -sN -X POST "$B/api/chat" -H "Content-Type: application/json" \
    -d "$(python -c "import json,sys; print(json.dumps({'message':sys.argv[1],'session_id':sys.argv[2]}))" "$msg" "$sid")" \
    --max-time 60
}

echo "=== S1 clarification (no district) ==="
post s-clar-1 "이 지역 요약" | grep -oE '"type":"[^"]+"|"action":"[^"]+"|clarifi|ambiguous' | head -20
echo

echo "=== S2 compare 2-way (과/를) ==="
post s-cmp-1 "강남역과 홍대입구를 비교해줘" | grep -oE '"type":"[^"]+"|"action":"compare"|"codes":\[[^]]+\]|compareList' | head -20
echo

echo "=== S3 compare 3-way ==="
post s-cmp-2 "강남역, 홍대입구, 건대입구 비교해줘" | grep -oE '"type":"[^"]+"|"action":"compare"|"codes":\[[^]]+\]' | head -20
echo

echo "=== S4 rewriter exclusion ==="
post s-cmp-3 "홍대 말고 성수역이랑 건대 비교" | grep -oE '"type":"[^"]+"|"action":"compare"|"codes":\[[^]]+\]' | head -20
echo
