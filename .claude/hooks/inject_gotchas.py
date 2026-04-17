#!/usr/bin/env python
"""SessionStart (compact): Re-inject MarketScope project gotchas.

Triggered after context compaction. Emits critical project-specific
conventions to stdout so Claude loads them into the fresh context.
"""
import sys

MSG = """[MarketScope 프로젝트 재주입 - 컨텍스트 압축 후 자동 로드]

1. SSE 포맷: `event:` 라인 없이 `type`이 `data:` JSON 안에 임베드됨. 표준 SSE 파서 금지, JSON 먼저 파싱할 것.
2. USE_MOCK: env 변수 필수 확인. Mock=D3001~D3005, Real=1650 districts. 값 불일치 시 tool 전체 실패.
3. Windows Python: 모든 file I/O에 `encoding='utf-8'` 명시. 실행 시 `PYTHONIOENCODING=utf-8`. 기본 cp949 깨짐.
4. Plan 작성: `docs/plan/<category>/`에 5섹션 구조(Checklist/재검토/Scenario/Pass반복/Agent모델)로 작성. `/plan-new` 스킬 사용 권장.
5. Memory 참조: 새 작업 시작 전 `memory/MEMORY.md` 훑고, 관련 feedback 파일명을 Plan Context에 인용.
"""


def main() -> None:
    try:
        sys.stdin.read()
    except Exception:
        pass
    print(MSG)
    sys.exit(0)


if __name__ == "__main__":
    main()
