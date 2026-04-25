#!/usr/bin/env python3
"""
run_matcher_tests.py — SentioCap Fuzzy Matcher Accuracy Runner

Runs all 50 messy test cases through the FuzzyMatcher and computes:
  - Overall accuracy
  - Accuracy by mess_type (abbreviation, synonym, jira_key, etc.)
  - Precision, Recall, F1
  - Auto-match rate (confidence >= 0.85)
  - False positive rate
  - Worst-performing mess types

Results are printed as a human-readable report and saved to a timestamped JSON.

Usage:
  cd /data/.openclaw/workspace/sentiocap
  python -m api.tests.run_matcher_tests

  # Or run a quick sanity check without saving:
  python -m api.tests.run_matcher_tests --no-save

  # Include slow AI-layer tests (requires Anthropic API key):
  python -m api.tests.run_matcher_tests --include-ai
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import logging
# Suppress noisy "_ai_match parse failed" warnings in fast/mock mode
logging.getLogger("api.services.fuzzy_matcher").setLevel(logging.ERROR)

from api.services.fuzzy_matcher import FuzzyMatcher, MatchResult
from api.tests.test_fuzzy_matcher import (
    MESSY_TEST_CASES,
    REFERENCE_INVESTMENTS,
    CROSS_SYSTEM_TESTS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTO_MATCH_THRESHOLD = 0.85
NEEDS_REVIEW_THRESHOLD = 0.50
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _investments_as_db_rows(investments: list[dict]) -> list[dict]:
    return [
        {
            "id": inv["id"],
            "name": inv["name"],
            "l2_category": inv["l2"],
            "description": inv["description"],
            "status": "active",
        }
        for inv in investments
    ]


def _build_matcher(include_ai: bool = False) -> FuzzyMatcher:
    """Build a FuzzyMatcher with a mocked DB. AI layer enabled/disabled via flag."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    mock_memory = AsyncMock()
    mock_memory.get_firm_glossary.return_value = []

    matcher = FuzzyMatcher(
        org_id="test-org",
        supabase_client=mock_db,
        memory=mock_memory,
    )

    if not include_ai:
        # Stub Anthropic so Layer 6 never fires — keeps tests fast & free
        mock_anthropic = MagicMock()
        matcher.client = mock_anthropic

    return matcher


def _is_correct(result: MatchResult, expected) -> bool:
    """
    Determine if a MatchResult is correct given the expected value.

    expected can be:
      - "inv-N"      → best_match.target_id == expected
      - "rtb-N"      → best_match.target_id == expected (RTB item match)
      - ["inv-A", "inv-B"] → split case: both IDs appear in candidates
      - "needs_review" → match_status in ("needs_review", "unmatched") OR confidence < 0.85
      - "unmatched"  → match_status == "unmatched" OR best_match confidence < 0.5
    """
    if expected == "unmatched":
        if result.best_match is None:
            return True
        return result.best_match.confidence < NEEDS_REVIEW_THRESHOLD

    if expected == "needs_review":
        if result.best_match is None:
            return True
        return result.best_match.confidence < AUTO_MATCH_THRESHOLD or result.needs_review

    if isinstance(expected, list):
        # Split case: all expected IDs should appear in candidates
        candidate_ids = {c.target_id for c in result.candidates}
        return all(eid in candidate_ids for eid in expected)

    # Single ID match
    if result.best_match is None:
        return False
    return result.best_match.target_id == expected


def _confidence_bucket(confidence: Optional[float]) -> str:
    if confidence is None:
        return "no_match"
    if confidence >= 0.85:
        return "auto_match"
    if confidence >= 0.50:
        return "needs_review"
    return "unmatched"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_all_tests(include_ai: bool = False) -> dict:
    """
    Run all 50 messy test cases and collect detailed results.
    Returns a full results dict suitable for JSON serialization and reporting.
    """
    matcher = _build_matcher(include_ai=include_ai)
    investments = _investments_as_db_rows(REFERENCE_INVESTMENTS)

    all_results = []
    errors = []

    print(f"\n{'═'*70}")
    print(f"  SentioCap Fuzzy Matcher — Accuracy Test Run")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  AI layer: {'ENABLED' if include_ai else 'MOCKED (fast mode)'}")
    print(f"{'═'*70}\n")

    for i, tc in enumerate(MESSY_TEST_CASES, 1):
        input_name = tc["input"]
        expected = tc["expected"]
        mess_type = tc["mess_type"]

        item = {
            "id": f"test-{i:03d}",
            "name": input_name,
            "type": "project",
        }

        t_start = time.monotonic()
        try:
            result = await matcher._match_single(
                item=item,
                source_system="jira",
                investments=investments,
                glossary=[],
                confirmed={},
            )
            elapsed_ms = (time.monotonic() - t_start) * 1000

            best_id = result.best_match.target_id if result.best_match else None
            best_conf = result.best_match.confidence if result.best_match else None
            best_method = result.best_match.match_method if result.best_match else None
            passed = _is_correct(result, expected)

            entry = {
                "case_num": i,
                "input": input_name,
                "expected": expected if isinstance(expected, str) else str(expected),
                "mess_type": mess_type,
                "actual_id": best_id,
                "actual_confidence": round(best_conf, 4) if best_conf is not None else None,
                "match_method": best_method,
                "match_status": result.match_status,
                "num_candidates": len(result.candidates),
                "passed": passed,
                "elapsed_ms": round(elapsed_ms, 2),
            }
            all_results.append(entry)

        except Exception as exc:
            elapsed_ms = (time.monotonic() - t_start) * 1000
            errors.append({"case_num": i, "input": input_name, "error": str(exc)})
            all_results.append({
                "case_num": i,
                "input": input_name,
                "expected": expected if isinstance(expected, str) else str(expected),
                "mess_type": mess_type,
                "actual_id": None,
                "actual_confidence": None,
                "match_method": "error",
                "match_status": "error",
                "num_candidates": 0,
                "passed": False,
                "elapsed_ms": round(elapsed_ms, 2),
                "error": str(exc),
            })

    return {
        "results": all_results,
        "errors": errors,
        "investments_count": len(REFERENCE_INVESTMENTS),
        "test_cases_count": len(MESSY_TEST_CASES),
        "include_ai": include_ai,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def compute_metrics(data: dict) -> dict:
    """Compute precision, recall, F1, accuracy by mess type, etc."""
    results = data["results"]
    total = len(results)

    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]

    # ── Overall accuracy ────────────────────────────────────────────────────
    overall_accuracy = len(passed) / total if total > 0 else 0.0

    # ── Auto-match stats ────────────────────────────────────────────────────
    auto_matched = [r for r in results if r.get("actual_confidence") and r["actual_confidence"] >= AUTO_MATCH_THRESHOLD]
    auto_matched_correct = [r for r in auto_matched if r["passed"]]
    auto_match_rate = len(auto_matched) / total if total > 0 else 0.0
    false_positive_rate = (
        (len(auto_matched) - len(auto_matched_correct)) / len(auto_matched)
        if auto_matched else 0.0
    )

    # ── Precision / Recall / F1 ─────────────────────────────────────────────
    # "relevant" = cases with a single expected investment ID (not split/ambiguous/unmatched)
    single_match_cases = [
        r for r in results
        if r["expected"].startswith("inv-") or r["expected"].startswith("rtb-")
    ]
    split_cases = [r for r in results if r["expected"].startswith("[")]
    ambiguous_cases = [r for r in results if r["expected"] in ("needs_review", "unmatched")]

    # True positives: expected a match and got the right one
    tp = sum(1 for r in single_match_cases if r["passed"] and r["actual_id"] is not None)
    # False positives: predicted a match but it was wrong (or not expected to match at all)
    fp = sum(1 for r in results if not r["passed"] and r["actual_id"] is not None and r["actual_confidence"] and r["actual_confidence"] >= NEEDS_REVIEW_THRESHOLD)
    # False negatives: expected a match but didn't get one (or got wrong ID)
    fn = sum(1 for r in single_match_cases if not r["passed"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    # ── Accuracy by mess_type ───────────────────────────────────────────────
    by_mess_type: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results:
        mt = r["mess_type"]
        by_mess_type[mt]["total"] += 1
        if r["passed"]:
            by_mess_type[mt]["passed"] += 1

    mess_type_accuracy = {
        mt: {
            "total": v["total"],
            "passed": v["passed"],
            "accuracy": round(v["passed"] / v["total"], 3) if v["total"] > 0 else 0.0,
        }
        for mt, v in sorted(by_mess_type.items())
    }

    # ── Worst-performing mess types ─────────────────────────────────────────
    worst_mess_types = sorted(
        mess_type_accuracy.items(),
        key=lambda x: x[1]["accuracy"],
    )[:5]

    # ── Match method distribution ───────────────────────────────────────────
    method_counts: dict[str, int] = defaultdict(int)
    for r in results:
        method_counts[r.get("match_method") or "no_match"] += 1

    # ── Confidence distribution ─────────────────────────────────────────────
    buckets: dict[str, int] = defaultdict(int)
    for r in results:
        buckets[_confidence_bucket(r.get("actual_confidence"))] += 1

    return {
        "total": total,
        "passed": len(passed),
        "failed": len(failed),
        "overall_accuracy": round(overall_accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "auto_match_rate": round(auto_match_rate, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "auto_matched_correct": len(auto_matched_correct),
        "auto_matched_total": len(auto_matched),
        "by_mess_type": mess_type_accuracy,
        "worst_mess_types": [
            {"mess_type": mt, **stats} for mt, stats in worst_mess_types
        ],
        "method_distribution": dict(method_counts),
        "confidence_buckets": dict(buckets),
        "errors": len(data["errors"]),
        "single_match_cases": len(single_match_cases),
        "split_cases": len(split_cases),
        "ambiguous_cases": len(ambiguous_cases),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(data: dict, metrics: dict) -> None:
    """Print a human-readable report to stdout."""
    results = data["results"]
    sep = "─" * 70

    # ── Per-case table ─────────────────────────────────────────────────────
    print(f"\n{'CASE-BY-CASE RESULTS':^70}")
    print(sep)
    print(f"{'#':>3}  {'PASS':^4}  {'CONF':^6}  {'METHOD':<18}  {'INPUT':<30}  EXPECTED → GOT")
    print(sep)

    for r in results:
        tick = "✓" if r["passed"] else "✗"
        conf_str = f"{r['actual_confidence']:.2f}" if r.get("actual_confidence") is not None else " —  "
        method = (r.get("match_method") or "none")[:18]
        input_str = r["input"][:30]
        expected_str = str(r["expected"])[:20]
        got_str = str(r.get("actual_id") or "none")[:20]
        flag = "" if r["passed"] else f"  ← expected {expected_str}"
        print(f"{r['case_num']:>3}  [{tick}]   {conf_str}  {method:<18}  {input_str:<30}  {got_str}{flag}")

    # ── Summary stats ──────────────────────────────────────────────────────
    print(f"\n{'SUMMARY STATISTICS':^70}")
    print(sep)
    print(f"  Total test cases      : {metrics['total']}")
    print(f"  Passed                : {metrics['passed']}  ({metrics['overall_accuracy']:.1%})")
    print(f"  Failed                : {metrics['failed']}")
    print(f"  Errors (exceptions)   : {metrics['errors']}")
    print()
    print(f"  Precision             : {metrics['precision']:.1%}  (correct matches / all attempted)")
    print(f"  Recall                : {metrics['recall']:.1%}  (correct matches / should have matched)")
    print(f"  F1 Score              : {metrics['f1_score']:.1%}")
    print()
    print(f"  Auto-match rate       : {metrics['auto_match_rate']:.1%}  ({metrics['auto_matched_total']} above {AUTO_MATCH_THRESHOLD:.0%} threshold)")
    print(f"  False positive rate   : {metrics['false_positive_rate']:.1%}  (wrong auto-matches)")
    print()

    # ── Confidence distribution ────────────────────────────────────────────
    print(f"  Confidence distribution:")
    for bucket, count in sorted(metrics["confidence_buckets"].items()):
        pct = count / metrics["total"] * 100
        bar = "█" * int(pct / 3)
        print(f"    {bucket:<15} {count:>3} ({pct:>5.1f}%) {bar}")
    print()

    # ── Match method distribution ──────────────────────────────────────────
    print(f"  Match method distribution:")
    for method, count in sorted(metrics["method_distribution"].items(), key=lambda x: -x[1]):
        pct = count / metrics["total"] * 100
        print(f"    {method:<25} {count:>3} ({pct:>5.1f}%)")
    print()

    # ── Accuracy by mess type ──────────────────────────────────────────────
    print(f"\n{'ACCURACY BY MESS TYPE':^70}")
    print(sep)
    print(f"  {'Mess Type':<25} {'Pass':>4} / {'Total':>5}  {'Accuracy':>8}  Bar")
    print(sep)
    for mt, stats in sorted(metrics["by_mess_type"].items(), key=lambda x: -x[1]["accuracy"]):
        acc = stats["accuracy"]
        bar = "█" * int(acc * 20)
        print(f"  {mt:<25} {stats['passed']:>4} / {stats['total']:>5}   {acc:>7.1%}  {bar}")

    # ── Worst performers ───────────────────────────────────────────────────
    print(f"\n{'WORST-PERFORMING MESS TYPES (areas to improve)':^70}")
    print(sep)
    for item in metrics["worst_mess_types"]:
        mt = item["mess_type"]
        acc = item["accuracy"]
        total = item["total"]
        print(f"  {mt:<25}  {acc:.0%} accuracy ({total} cases)")
        # Show failing cases for this mess type
        fails = [r for r in results if r["mess_type"] == mt and not r["passed"]]
        for f in fails[:3]:
            print(f"    ✗ '{f['input']}' → expected {f['expected']}, got {f.get('actual_id') or 'none'} ({f.get('actual_confidence') or '—'})")

    print(f"\n{'═'*70}")

    # ── Final verdict ──────────────────────────────────────────────────────
    acc = metrics["overall_accuracy"]
    if acc >= 0.80:
        verdict = "✅ EXCELLENT — Production quality matching"
    elif acc >= 0.65:
        verdict = "🟡 GOOD — AI layer would push this over the bar"
    elif acc >= 0.50:
        verdict = "🟠 FAIR — Several mess types need improvement"
    else:
        verdict = "🔴 NEEDS WORK — Core matching not performing well"

    print(f"\n  Overall Accuracy: {acc:.1%}   {verdict}")
    print(f"  F1 Score:         {metrics['f1_score']:.1%}")
    print(f"  Auto-match FP:    {metrics['false_positive_rate']:.1%}  (target: < 5%)")
    print(f"\n{'═'*70}\n")


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(data: dict, metrics: dict) -> str:
    """Save results to a JSON file. Returns the file path."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"matcher_results_{ts}.json")
    payload = {
        "run_at": data["run_at"],
        "include_ai": data["include_ai"],
        "metrics": metrics,
        "test_cases": data["results"],
        "errors": data["errors"],
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# Cross-system accuracy report
# ---------------------------------------------------------------------------

async def run_cross_system_check(matcher: FuzzyMatcher, investments: list[dict]) -> dict:
    """
    Run cross-system entity resolution tests and report how often
    the same investment is top-1 across all three systems.
    """
    print(f"\n{'CROSS-SYSTEM ENTITY RESOLUTION CHECK':^70}")
    print("─" * 70)

    results = []
    for tc in CROSS_SYSTEM_TESTS:
        expected = tc["expected_investment"]
        row = {"expected": expected, "systems": {}}
        for system, name in [
            ("salesforce", tc["salesforce"]),
            ("jira", tc["jira"]),
            ("gl", tc["gl"]),
        ]:
            item = {"id": f"cross-{system}-{name[:8]}", "name": name, "type": "product" if system == "salesforce" else "project"}
            result = await matcher._match_single(
                item=item,
                source_system=system,
                investments=investments,
                glossary=[],
                confirmed={},
            )
            candidate_ids = [c.target_id for c in result.candidates]
            hit = expected in candidate_ids
            row["systems"][system] = {
                "name": name,
                "top1": result.best_match.target_id if result.best_match else None,
                "top1_correct": result.best_match.target_id == expected if result.best_match else False,
                "in_candidates": hit,
                "confidence": result.best_match.confidence if result.best_match else None,
            }
        results.append(row)

    # Print per-test summary
    all_3_correct = 0
    for row in results:
        exp = row["expected"]
        flags = []
        for sys, info in row["systems"].items():
            sym = "✓" if info["top1_correct"] else ("~" if info["in_candidates"] else "✗")
            flags.append(f"{sys[:2].upper()}:{sym}")
        if all(info["top1_correct"] for info in row["systems"].values()):
            all_3_correct += 1
        print(f"  {exp:<10}  {' '.join(flags)}")

    pct = all_3_correct / len(results) * 100 if results else 0
    print(f"\n  All-3-correct: {all_3_correct}/{len(results)} ({pct:.0f}%)")
    return {"all_3_correct": all_3_correct, "total": len(results)}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SentioCap Fuzzy Matcher Accuracy Runner")
    parser.add_argument("--include-ai", action="store_true", help="Enable Layer 6 AI matching (slow, requires ANTHROPIC_API_KEY)")
    parser.add_argument("--no-save", action="store_true", help="Skip saving results to JSON")
    parser.add_argument("--cross-system", action="store_true", default=True, help="Include cross-system entity resolution check")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    # Run main test suite
    data = loop.run_until_complete(run_all_tests(include_ai=args.include_ai))
    metrics = compute_metrics(data)
    print_report(data, metrics)

    # Cross-system check
    if args.cross_system:
        matcher = _build_matcher(include_ai=args.include_ai)
        investments = _investments_as_db_rows(REFERENCE_INVESTMENTS)
        cross_results = loop.run_until_complete(run_cross_system_check(matcher, investments))
        metrics["cross_system"] = cross_results

    # Save results
    if not args.no_save:
        path = save_results(data, metrics)
        print(f"  Results saved to: {path}\n")
    else:
        print("  (Results not saved — pass without --no-save to persist)\n")

    # Exit code: 0 = all passed, 1 = some failures
    sys.exit(0 if metrics["failed"] == 0 and metrics["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
