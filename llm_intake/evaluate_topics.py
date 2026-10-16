"""Opakovatelné živé ověření témat na syntetických případech mimo prompt."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

from .client import APIError, Client
from .master import MasterExtractor, analyze_message
from .master_contract import MessageEvent
from .question_catalog import load_topic_catalog

CASES = Path(__file__).resolve().parents[1] / "tests/fixtures/master_topic_cases.json"


def evaluate_case(case: dict, extractor) -> dict:
    message = MessageEvent(
        f"synthetic-eval-{case['id']}",
        "synthetic-patient",
        case["text"],
        "2026-10-16T10:00:00+02:00",
        "master_question",
        case.get("author", "patient"),
        "Jak se dnes cítíte?",
    )
    expected = set(case["expected_topics"])
    row = {"id": case["id"], "text": case["text"], "expected_topics": sorted(expected)}
    usage = []
    if isinstance(extractor, MasterExtractor) and isinstance(extractor.client, Client):
        extractor = MasterExtractor(replace(extractor.client, on_usage=usage.append))
    row["api_usage"] = usage
    try:
        packet = analyze_message(message, extractor)
        actual = {topic for fact in packet["facts"] for topic in fact["topic_ids"]}
        candidates = {
            f"{c['question']['questionnaire_id']}/{c['question']['question_id']}"
            for c in packet["question_candidates"]
        }
        forbidden = candidates.intersection(case.get("forbidden_candidates", []))
        unexpected = (
            actual - set(case["allowed_topics"]) if "allowed_topics" in case else set()
        )
        failed_facts = [
            check
            for check in case.get("fact_checks", [])
            if not any(
                check["topic_id"] in fact["topic_ids"]
                and all(
                    fact.get(key) == value
                    for key, value in check.items()
                    if key != "topic_id"
                )
                for fact in packet["facts"]
            )
        ]
        unmapped_missing = bool(
            case.get("expected_unmapped") and not packet["unmapped_concepts"]
        )
        row.update(
            {
                "actual_topics": sorted(actual),
                "missing_topics": sorted(expected - actual),
                "extra_topics": sorted(actual - expected),
                "forbidden_candidates": sorted(forbidden),
                "unexpected_topics": sorted(unexpected),
                "precision_labelled": "allowed_topics" in case,
                "failed_fact_checks": failed_facts,
                "missing_unmapped_finding": unmapped_missing,
                "facts": packet["facts"],
                "passed": not (
                    expected - actual
                    or forbidden
                    or unmapped_missing
                    or unexpected
                    or failed_facts
                ),
            }
        )
    except (APIError, ValueError, TypeError) as exc:
        row.update(
            {
                "error": str(exc),
                "error_type": "api" if isinstance(exc, APIError) else "validation",
                "missing_topics": sorted(expected),
                "passed": False,
            }
        )
    return row


def summarize(rows: list[dict]) -> dict:
    evaluated = [row for row in rows if "error" not in row]
    expected = sum(len(row["expected_topics"]) for row in evaluated)
    missing = sum(len(row["missing_topics"]) for row in evaluated)
    calls = [call for row in rows for call in row.get("api_usage", [])]
    labelled = [row for row in evaluated if row.get("precision_labelled")]
    predicted = sum(len(row["actual_topics"]) for row in labelled)
    unexpected = sum(len(row["unexpected_topics"]) for row in labelled)
    return {
        "type": "synthetic_regression",
        "catalogue_size": len(load_topic_catalog()),
        "cases": len(rows),
        "evaluated_cases": len(evaluated),
        "error_cases": len(rows) - len(evaluated),
        "passed": sum(row["passed"] for row in rows),
        "evaluated_topic_mentions": expected,
        "missing_topic_mentions": missing,
        "topic_recall": (expected - missing) / expected if expected else None,
        "extra_topic_mentions": sum(len(row.get("extra_topics", [])) for row in rows),
        "precision_labelled_cases": len(labelled),
        "labelled_topic_predictions": predicted,
        "unexpected_topic_mentions": unexpected,
        "topic_precision": (predicted - unexpected) / predicted if predicted else None,
        "api_usage": {
            "reported_calls": len(calls),
            "calls_with_token_usage": sum(
                call.get("prompt_tokens") is not None for call in calls
            ),
            **{
                key: sum(call[key] for call in calls if call.get(key) is not None)
                if any(call.get(key) is not None for call in calls)
                else None
                for key in (
                    "prompt_tokens",
                    "completion_tokens",
                    "cached_tokens",
                    "reasoning_tokens",
                )
            },
        },
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Živá syntetická regrese pokrytí MASTER témat"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        action="append",
        help="Sada případů; lze opakovat (výchozí sada pokrytí)",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Vybrané ID případu; lze opakovat",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--output", type=Path, default=Path(".scratch/master-topics-evaluation.json")
    )
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and args.limit < 1):
        parser.error("workers a limit musí být kladné")
    cases = [
        case
        for path in (args.cases or [CASES])
        for case in json.loads(path.read_text(encoding="utf-8"))
    ]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        parser.error("Sady musejí obsahovat případy s jednoznačnými ID")
    if args.case_ids:
        if not set(args.case_ids) <= {c["id"] for c in cases}:
            parser.error("Neznámé ID případu")
        cases = [c for c in cases if c["id"] in args.case_ids]
    if args.limit is not None:
        cases = cases[: args.limit]
    extractor = MasterExtractor(Client.from_env())
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(evaluate_case, case, extractor) for case in cases]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(
                f"{len(rows)}/{len(cases)} {'OK' if row['passed'] else 'FAIL'} {row['id']}",
                flush=True,
            )
    order = {c["id"]: i for i, c in enumerate(cases)}
    rows.sort(key=lambda row: order[row["id"]])
    result = summarize(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Passed {result['passed']}/{result['cases']}; errors {result['error_cases']}; "
        f"topic recall on evaluated cases {result['topic_recall']}; "
        f"precision on labelled cases {result['topic_precision']}; {args.output}"
    )
    return 0 if result["passed"] == result["cases"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
