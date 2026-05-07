"""W1 entity-matching adversarial eval — Plan: docs/plan/fix/w1-type-boost-tuning-2026-05-06.md.

Reads a YAML adversarial dataset, calls ``rank_candidates`` + ``pick_best``,
and reports per-class accuracy + boost diagnostics. Optionally sweeps the
``_MARKET_TYPE_BOOST`` and ``_PAREN_ALIAS_ONLY_DAMP`` constants.

Usage::

    python server/scripts/w1_eval.py
    python server/scripts/w1_eval.py --sweep
    python server/scripts/w1_eval.py --dataset path/to/other.yaml
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

# Make `server` package importable when invoked as `python server/scripts/...`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.agent.utils import entity_matching as em  # noqa: E402


def evaluate(dataset_path: Path) -> dict:
    cases = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))["cases"]
    by_class: dict[str, list[dict]] = defaultdict(list)
    failures: list[dict] = []

    for case in cases:
        cls = case["id"].split("-")[0]
        rows = [(c[0], c[1], c[2]) for c in case["candidates"]]
        ranked = em.rank_candidates(case["query"], rows)
        best, _alts, _amb = em.pick_best(ranked)
        actual = best.code if best else None
        expected = case["expected_top1_code"]
        passed = actual == expected
        record = {
            "id": case["id"],
            "class": cls,
            "query": case["query"],
            "expected": expected,
            "actual": actual,
            "actual_score": round(best.score, 4) if best else None,
            "passed": passed,
        }
        by_class[cls].append(record)
        if not passed:
            failures.append(record)

    total = sum(len(v) for v in by_class.values())
    passed_total = sum(1 for v in by_class.values() for r in v if r["passed"])

    return {
        "total": total,
        "passed": passed_total,
        "accuracy": passed_total / total if total else 0.0,
        "by_class": {
            cls: {
                "total": len(records),
                "passed": sum(1 for r in records if r["passed"]),
            }
            for cls, records in by_class.items()
        },
        "failures": failures,
    }


def print_report(result: dict, label: str = "baseline") -> None:
    print(f"=== W1 Adversarial Eval — {label} ===")
    print(
        f"  market_boost={em._MARKET_TYPE_BOOST}  "
        f"paren_alias_damp={em._PAREN_ALIAS_ONLY_DAMP}  "
        f"paren_exact={em._PAREN_EXACT_BONUS}"
    )
    print(f"  Total: {result['passed']}/{result['total']}  ({result['accuracy'] * 100:.1f}%)")
    for cls in sorted(result["by_class"]):
        b = result["by_class"][cls]
        print(f"    {cls}: {b['passed']}/{b['total']}")
    if result["failures"]:
        print("  FAIL:")
        for f in result["failures"]:
            print(
                f"    [{f['id']}] '{f['query']}' "
                f"expected={f['expected']} actual={f['actual']} score={f['actual_score']}"
            )
    print()


def sweep(dataset_path: Path) -> list[dict]:
    """Run the eval across a 4×3 grid of (market_boost, paren_alias_damp).

    Mutates the module-level constants temporarily — single-process, single-
    threaded so this is safe in this script. Restores originals at the end.
    """
    boosts = [0.05, 0.10, 0.15, 0.20]
    damps = [0.30, 0.50, 0.70]  # multiplicative factor on _PAREN_EXACT_BONUS

    orig_boost = em._MARKET_TYPE_BOOST
    orig_damp = em._PAREN_ALIAS_ONLY_DAMP

    rows: list[dict] = []
    try:
        for b in boosts:
            for d in damps:
                em._MARKET_TYPE_BOOST = b
                em._PAREN_ALIAS_ONLY_DAMP = d
                result = evaluate(dataset_path)
                rows.append(
                    {
                        "boost": b,
                        "damp": d,
                        "accuracy": result["accuracy"],
                        "passed": result["passed"],
                        "total": result["total"],
                        "fail_classes": dict(Counter(f["class"] for f in result["failures"])),
                    }
                )
    finally:
        em._MARKET_TYPE_BOOST = orig_boost
        em._PAREN_ALIAS_ONLY_DAMP = orig_damp
    return rows


def print_sweep(rows: list[dict]) -> None:
    print("=== W1 Sweep — (market_boost × paren_alias_damp) ===")
    print(f"  {'boost':>8} {'damp':>8} {'acc':>8} {'passed':>8}/{'total':<5}  failed_classes")
    rows_sorted = sorted(rows, key=lambda r: r["accuracy"], reverse=True)
    for r in rows_sorted:
        cls = ", ".join(f"{k}:{v}" for k, v in sorted(r["fail_classes"].items()))
        print(
            f"  {r['boost']:>8.2f} {r['damp']:>8.2f} "
            f"{r['accuracy'] * 100:>7.1f}% {r['passed']:>8}/{r['total']:<5}  {cls}"
        )
    if rows_sorted:
        best = rows_sorted[0]
        print(f"\n  Best: boost={best['boost']} damp={best['damp']} → accuracy={best['accuracy'] * 100:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser()
    default_dataset = ROOT / "tests" / "data" / "w1_adversarial_2026-05-06.yaml"
    parser.add_argument("--dataset", type=Path, default=default_dataset)
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Dataset not found: {args.dataset}", file=sys.stderr)
        return 2

    if args.sweep:
        print_sweep(sweep(args.dataset))
    else:
        print_report(evaluate(args.dataset))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
