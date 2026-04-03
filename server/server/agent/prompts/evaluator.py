"""Evaluator prompt — judge whether tool results are sufficient."""

EVALUATOR_PROMPT = """\
도구 실행 결과가 사용자 질문에 답하기에 충분한지 판단하세요.

## 사용자 질문
{user_message}

## 의도
{intent}

## 도구 결과 요약
{tool_results_summary}

## 도구 에러
{tool_errors}

## 판단 기준
- 사용자 질문에 답변할 수 있는 핵심 데이터가 있는가?
- 에러가 있다면 답변 품질에 치명적인가?
- 추가 도구 호출로 보완할 수 있는 부분이 있는가?

## 출력 (JSON만, 다른 텍스트 없이)
{{"sufficient": true, "missing_info": [], "reasoning": "판단 근거"}}
"""
