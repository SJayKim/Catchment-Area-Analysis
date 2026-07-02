"""Model-driven agentic loop (v2) — Planner/Evaluator replaced by a native
function-calling loop with a Trust Kernel.

Design: docs/plan/infra/general-agentic-loop-redesign-2026-06-27.md

Modules:
  models.py  — LLM factory + provider fallback chain (no hardcoded model IDs)
  tools_fc.py— function-calling tool schemas + executor (+ compute/abstain/resolve)
  trust.py   — fact pool + numeric binding gate (reuses utils/numeric_sanity)
  prompts.py — grounded-answer-contract system prompt
  engine.py  — the loop itself (exposes run_agent, same SSE contract as PAE)
"""
