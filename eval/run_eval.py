"""
run_eval.py — End-to-end golden eval runner.

Reads backend/tests/eval_cases.json, fires each case at the running FastAPI server,
and prints a pass/fail report.

Usage:
  python eval/run_eval.py [--base-url http://localhost:8000]
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

EVAL_FILE = Path(__file__).parent.parent / "backend" / "tests" / "eval_cases.json"


def check_case(case: dict, response: dict) -> tuple[bool, str]:
    """
    Evaluate one case against the agent response.

    Returns (passed: bool, reason: str).
    """
    behavior = case.get("expected_behavior", "answer_contains")
    answer = (response.get("answer") or "").lower()
    proposed = response.get("proposed_action")

    if behavior == "answer_contains":
        for kw in case.get("expected", []):
            if kw.lower() not in answer:
                return False, f"Missing expected keyword: '{kw}'"
        for kw in case.get("must_not_contain", []):
            if kw.lower() in answer:
                return False, f"Found forbidden keyword: '{kw}'"
        return True, "ok"

    elif behavior == "proposed_action_present":
        if not proposed:
            return False, "Expected a proposed_action but got None"
        for kw in case.get("must_not_contain", []):
            if kw.lower() in answer:
                return False, f"Found forbidden keyword in answer: '{kw}'"
        return True, "ok"

    elif behavior == "does_not_error":
        if "error" in answer or "denied" in answer:
            for kw in case.get("must_not_contain", []):
                if kw.lower() in answer:
                    return False, f"Found forbidden keyword: '{kw}'"
        return True, "ok"

    return False, f"Unknown expected_behavior: {behavior}"


def run_eval(base_url: str):
    with open(EVAL_FILE, encoding="utf-8") as f:
        cases = json.load(f)

    passed = 0
    failed = 0
    errors = 0

    print(f"\n{'='*60}")
    print(f"  ParcelPilot Eval — {len(cases)} cases  →  {base_url}")
    print(f"{'='*60}\n")

    for case in cases:
        cid = case["id"]
        desc = case["description"]

        try:
            resp = httpx.post(
                f"{base_url}/chat",
                json={
                    "account_id": case["account_id"],
                    "message": case["question"],
                    "history": [],
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"  [ERROR] {cid}: {desc}")
            print(f"          HTTP error: {exc}\n")
            errors += 1
            continue

        ok, reason = check_case(case, data)

        if ok:
            print(f"  [PASS ] {cid}: {desc}")
            passed += 1
        else:
            print(f"  [FAIL ] {cid}: {desc}")
            print(f"          Reason : {reason}")
            print(f"          Answer : {data.get('answer','')[:200]}")
            print(f"          Tools  : {data.get('tools_used', [])}\n")
            failed += 1

    total = passed + failed + errors
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} passed  |  {failed} failed  |  {errors} errors")
    print(f"{'='*60}\n")

    return failed + errors


def main():
    parser = argparse.ArgumentParser(description="ParcelPilot golden eval runner")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the running FastAPI server (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    exit_code = run_eval(args.base_url)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
