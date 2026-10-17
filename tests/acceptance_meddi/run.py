"""Validate the source-based suite or grade a separately supplied real adapter.

No application/LLM imports until an adapter is explicitly requested. This file
is deliberately not named test_*.py: unfinished acceptance work must not be
mistaken for an existing green application regression suite.
"""

import argparse
import hashlib
import importlib
import json
import re
import smtplib
import socket
import sys
from collections import Counter
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
STEPS = {
    1: "dalsi_sledovani",
    2: "kontaktovat_tym",
    3: "telekonzultace",
    4: "neodkladna_pomoc",
}
CHECKS = {
    "level_min",
    "level_max",
    "observations_subset",
    "must_not_infer",
    "forbidden_observation_values",
    "require_evidence",
    "literal_evidence_required",
    "forbid_invented_numbers",
    "needs_review",
    "follow_up_required",
    "conflict_required",
    "reminder_required",
    "team_notification_required",
    "urgent_before_confirmation",
    "urgent_before_targeted_llm",
    "urgent_instruction_forbidden",
    "phone",
    "route",
    "before_next_dose",
    "same_day_contact",
    "palliative_route_required",
    "fallback_155_required",
    "patient_safety_net_required",
    "no_future_evidence",
    "forbidden_used_event_ids",
    "address_caregiver",
    "advance_wishes_must_not_block_help",
    "no_new_drug_dose",
}


def read_json(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def read_rows(name):
    return [
        json.loads(line)
        for line in (HERE / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def instant(stamp):
    result = datetime.fromisoformat(stamp)
    if result.utcoffset() is None:
        raise ValueError(f"Timestamp without timezone: {stamp}")
    return result


def input_path(raw, path):
    result = raw
    for key in path.strip("/").split("/"):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def validate():
    sources = read_json("sources.json")["sources"]
    for identifier, source in sources.items():
        path = ROOT / source["path"]
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]
        ):
            raise ValueError(
                f"Source missing or changed: {identifier}; review the source instead of blindly updating its hash"
            )
    raw_rows, expected_rows = read_rows("inputs.jsonl"), read_rows("expectations.jsonl")
    raw = {row["id"]: row for row in raw_rows}
    expected = {row["id"]: row for row in expected_rows}
    requirements = read_json("requirements.json")["requirements"]
    req_ids = {r["id"] for r in requirements}
    if (
        len(raw) != len(raw_rows)
        or len(expected) != len(expected_rows)
        or len(req_ids) != len(requirements)
    ):
        raise ValueError("Duplicate identifier")
    if raw.keys() != expected.keys():
        raise ValueError("Input and expectation identifiers differ")
    covered = set()
    for identifier, target in expected.items():
        if not target["sources"] or not set(target["requirement_ids"]) <= req_ids:
            raise ValueError(f"Missing source/requirement: {identifier}")
        covered.update(target["requirement_ids"])
        for source in target["sources"]:
            if source["source_id"] not in sources or not source["locator"].strip():
                raise ValueError(f"Invalid source: {identifier}")
        if target["grading"] not in {"automatic", "clinical_review", "human_review"}:
            raise ValueError(f"Invalid grading: {identifier}")
        checks = target["checks"]
        if set(checks) - CHECKS:
            raise ValueError(
                f"Unsupported checks in {identifier}: {set(checks) - CHECKS}"
            )
        for field in ("level_min", "level_max"):
            if checks.get(field) is not None and (
                type(checks[field]) is not int or not 1 <= checks[field] <= 4
            ):
                raise ValueError(f"Invalid level bound: {identifier}")
        if (
            checks.get("level_min") is not None
            and checks.get("level_max") is not None
            and checks["level_min"] > checks["level_max"]
        ):
            raise ValueError(f"Contradictory bounds: {identifier}")
        sample = raw[identifier]
        if set(sample) & {
            "checks",
            "grading",
            "expected",
            "sources",
            "requirement_ids",
            "review_notes",
        }:
            raise ValueError(f"Reference metadata leaked into input: {identifier}")
        if sample.get("assessment_at"):
            instant(sample["assessment_at"])
        events = [*sample["events"], *sample["history"]]
        if len({e["id"] for e in events}) != len(events):
            raise ValueError(f"Duplicate event: {identifier}")
        for event in events:
            if event.get("available_at"):
                instant(event["available_at"])
        if set(checks.get("must_not_infer", [])) & {
            k for k, v in checks.get("observations_subset", {}).items() if v is not None
        }:
            raise ValueError(
                f"Same observation both required and forbidden: {identifier}"
            )
    if covered != req_ids:
        raise ValueError(f"Uncovered requirements: {req_ids - covered}")
    coverage = read_json("coverage.json")["coverage"]
    for row in coverage:
        if (
            not row["requirement_ids"]
            or not set(row["requirement_ids"]) <= req_ids
            or not row["case_ids"]
            or not set(row["case_ids"]) <= raw.keys()
        ):
            raise ValueError(f"Invalid coverage row: {row['source_scope']}")
    for scope in ("Červená", "Oranžová"):
        rules = (ROOT / sources["rules"]["path"]).read_text(encoding="utf-8")
        section = rules.split("### " + scope, 1)[1].split("\n##", 1)[0]
        for line in section.splitlines():
            if line.startswith("| ") and not line.startswith("| Oblast"):
                area = line.split("|")[1].strip()
                if f"§3 / {scope} / {area}" not in {
                    c["source_scope"] for c in coverage
                }:
                    raise ValueError(f"Uncovered hard-rule row: {scope}/{area}")
    return sources, raw, expected


def grade(raw, expected, actual):
    """Check observable output; review is never converted into PASS."""
    failures = []
    check = expected["checks"]

    def require(condition, message):
        if not condition:
            failures.append(message)

    if not isinstance(actual, dict):
        return {"status": "FAIL", "failures": ["Adapter did not return an object"]}
    level = actual.get("level")
    valid_level = type(level) is int and 1 <= level <= 4
    require(valid_level, "Missing/invalid level 1–4")
    if valid_level:
        if check.get("level_min") is not None:
            require(
                level >= check["level_min"],
                f"Level {level} below required minimum {check['level_min']}",
            )
        if check.get("level_max") is not None:
            require(
                level <= check["level_max"],
                f"Level {level} above permitted maximum {check['level_max']}",
            )
        require(
            actual.get("next_step") == STEPS[level],
            "Wrong next step for resulting level",
        )
        require(
            actual.get("team_notification_required") is (level >= 2),
            "Notification requirement does not match level",
        )
    observations = actual.get("observations") or {}
    for field, value in check.get("observations_subset", {}).items():
        present = field in observations and observations[field] == value
        if type(value) is bool:
            present = field in observations and observations[field] is value
        require(
            present,
            f"Observation {field}: expected {value!r}, got {observations.get(field)!r}",
        )
    for field in check.get("must_not_infer", []):
        require(
            observations.get(field) is None,
            f"Invented/unsupported observation: {field}",
        )
    for field, value in check.get("forbidden_observation_values", {}).items():
        require(
            field not in observations or observations[field] != value,
            f"Negated/context-only symptom treated as present: {field}",
        )
    if check.get("forbid_invented_numbers"):
        allowed = {
            v
            for v in check.get("observations_subset", {}).values()
            if type(v) in {int, float}
        }
        allowed.update(
            v for v in raw["patient_context"].values() if type(v) in {int, float}
        )
        for field, value in observations.items():
            if type(value) in {int, float}:
                require(
                    value in allowed,
                    f"Unsupported additional numeric observation {field}={value}",
                )
    at = instant(raw["assessment_at"]) if raw.get("assessment_at") else None
    events = {e["id"]: e for e in [*raw["events"], *raw["history"]]}
    eligible = {
        i
        for i, e in events.items()
        if not at or not e.get("available_at") or instant(e["available_at"]) <= at
    }
    evidence = actual.get("evidence") or []
    if check.get("require_evidence"):
        require(bool(evidence), "Missing evidence for a clinical finding")
    for item in evidence:
        if item.get("event_id"):
            require(
                item["event_id"] in eligible, "Evidence from an unknown/future event"
            )
            if item.get("quote") is not None and item["event_id"] in events:
                require(
                    bool(item["quote"])
                    and item["quote"] in events[item["event_id"]].get("text", ""),
                    "Evidence quote is not literal",
                )
        elif item.get("input_path"):
            try:
                input_path(raw, item["input_path"])
                parts = item["input_path"].strip("/").split("/")
                if parts[0] in {"events", "history"}:
                    event = raw[parts[0]][int(parts[1])]
                    require(
                        event["id"] in eligible,
                        "Evidence path points to a future event",
                    )
            except (KeyError, IndexError, TypeError, ValueError):
                require(False, "Evidence path is not present in test input")
        else:
            require(False, "Evidence has neither event_id nor input_path")
    if check.get("literal_evidence_required"):
        require(
            any(e.get("quote") and e.get("event_id") in eligible for e in evidence),
            "Missing original-language literal citation",
        )
    used = set(actual.get("used_event_ids") or [])
    require(used <= eligible, "Future or unknown event used")
    require(
        not used.intersection(check.get("forbidden_used_event_ids", [])),
        "Forbidden event used",
    )
    if check.get("no_future_evidence"):
        require(
            "used_event_ids" in actual and "llm_requests" in actual,
            "Temporal test requires captured event use and actual LLM requests",
        )
        for identifier in events.keys() - eligible:
            canary = events[identifier].get("text", "")
            require(
                not canary
                or all(
                    canary not in json.dumps(payload, ensure_ascii=False)
                    for payload in actual.get("llm_requests", [])
                ),
                "Future text leaked into an LLM request",
            )
    for field in ("needs_review", "team_notification_required", "reminder_required"):
        if field in check:
            require(actual.get(field) is check[field], f"Wrong {field}")
    if check.get("follow_up_required"):
        require(
            bool(actual.get("follow_up_questions")), "Missing clarification question"
        )
    if check.get("conflict_required"):
        require(
            bool(actual.get("conflicts")),
            "Message/questionnaire contradiction not recorded",
        )
    trace = actual.get("trace") or []
    kinds = [event.get("kind") for event in trace]
    urgent = [i for i, k in enumerate(kinds) if k == "urgent_instruction"]
    if check.get("urgent_instruction_forbidden"):
        require(
            not urgent and (not valid_level or level < 3),
            "Unfounded urgent instruction/escalation",
        )
    for flag, later in (
        ("urgent_before_targeted_llm", "targeted_llm"),
        ("urgent_before_confirmation", "confirm"),
    ):
        if check.get(flag):
            require(bool(urgent), "Missing observed urgent instruction")
            require(
                all(i > urgent[0] for i, k in enumerate(kinds) if k == later)
                if urgent
                else False,
                f"{later} preceded urgent instruction",
            )
    route = actual.get("routing") or {}
    phone = re.sub(r"\D", "", str(route.get("phone") or ""))
    patient_text = str(actual.get("patient_text") or "")
    if check.get("phone"):
        require(phone == re.sub(r"\D", "", check["phone"]), "Wrong urgent phone number")
    due = instant(route["response_due_at"]) if route.get("response_due_at") else None
    route_checks = check.get("route") or {}
    if route_checks.get("phone"):
        require(phone == route_checks["phone"], "Wrong in/out-of-hours phone")
    if "working_hours" in route_checks:
        require(
            route.get("within_working_hours") is route_checks["working_hours"],
            "Wrong working-hours classification",
        )
    if route_checks.get("response_due_at"):
        require(
            due == instant(route_checks["response_due_at"]), "Wrong response deadline"
        )
    if route_checks.get("max_response_seconds") is not None:
        require(
            due is not None
            and at is not None
            and 0 <= (due - at).total_seconds() <= route_checks["max_response_seconds"],
            "Response deadline exceeds protocol",
        )
    if route_checks.get("team_notify_seconds"):
        team_due = (
            instant(route["team_notify_by"]) if route.get("team_notify_by") else None
        )
        require(
            team_due is not None
            and at is not None
            and 0
            <= (team_due - at).total_seconds()
            <= route_checks["team_notify_seconds"],
            "Team notification deadline exceeds protocol",
        )
    if check.get("same_day_contact"):
        require(
            due is not None
            and at is not None
            and due >= at
            and due.astimezone(ZoneInfo("Europe/Prague")).date()
            <= at.astimezone(ZoneInfo("Europe/Prague")).date(),
            "Specific same-day requirement replaced by next workday",
        )
    if check.get("before_next_dose"):
        require(
            route.get("before_next_dose") is True, "Missing before-next-dose constraint"
        )
    if check.get("palliative_route_required"):
        require(
            route.get("contact_code") in {"palliative_team_24h", "emergency"},
            "Missing palliative/emergency help",
        )
    if check.get("fallback_155_required") or check.get(
        "advance_wishes_must_not_block_help"
    ):
        require("155" in patient_text or phone == "155", "Missing emergency fallback")
    if check.get("patient_safety_net_required"):
        require(
            "155" in patient_text and "724" in patient_text,
            "Missing worsening/emergency safety net",
        )
    # These semantic requirements remain for a person; never trust a returned
    # 'passed=true' or infer absence of a drug change just from a model's claim.
    needs_human = (
        expected["grading"] != "automatic"
        or check.get("address_caregiver")
        or check.get("no_new_drug_dose")
    )
    return {
        "status": "FAIL" if failures else "REVIEW_REQUIRED" if needs_human else "PASS",
        "failures": failures,
    }


def blocked_network(*args, **kwargs):
    raise RuntimeError(
        "Network disabled for acceptance tests; use an explicit LLM-only adapter and --allow-network if authorized"
    )


@contextmanager
def network_guard(allow_network):
    with ExitStack() as stack:
        stack.enter_context(patch.object(smtplib, "SMTP", blocked_network))
        stack.enter_context(patch.object(smtplib, "SMTP_SSL", blocked_network))
        if not allow_network:
            stack.enter_context(patch.object(socket.socket, "connect", blocked_network))
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["validate", "list", "evaluate", "self-check"]
    )
    parser.add_argument(
        "--adapter", help="Separate module:function accepting ONLY the input object"
    )
    parser.add_argument("--tag", help="Filter by tag, e.g. required-six or boundary")
    parser.add_argument("--id", help="Filter by case-ID prefix")
    parser.add_argument(
        "--grading", choices=["automatic", "clinical_review", "human_review"]
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Permit explicitly authorized live LLM calls, SMTP remains blocked",
    )
    args = parser.parse_args()
    sources, inputs, expected = validate()
    selected = [
        e
        for e in expected.values()
        if (not args.tag or args.tag in e["tags"])
        and (not args.id or e["id"].startswith(args.id))
        and (not args.grading or e["grading"] == args.grading)
    ]
    if args.command == "validate":
        print(
            json.dumps(
                {
                    "fixture_validation": "passed",
                    "cases": len(inputs),
                    "requirements": len(read_json("requirements.json")["requirements"]),
                    "grading": dict(Counter(e["grading"] for e in expected.values())),
                    "application_tests_executed": 0,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "self-check":
        sample_id = "RED-FEVER.message"
        bad = {
            "level": 1,
            "next_step": STEPS[1],
            "team_notification_required": False,
            "observations": {},
        }
        result = grade(inputs[sample_id], expected[sample_id], bad)
        assert result["status"] == "FAIL" and any(
            "below required" in f for f in result["failures"]
        )
        assert any("Observation" in f for f in result["failures"])
        good = {
            "level": 4,
            "next_step": STEPS[4],
            "team_notification_required": True,
            "observations": deepcopy(
                expected[sample_id]["checks"]["observations_subset"]
            ),
            "evidence": [
                {"event_id": "opening", "quote": inputs[sample_id]["events"][0]["text"]}
            ],
        }
        assert grade(inputs[sample_id], expected[sample_id], good)["status"] == "PASS"
        review = deepcopy(expected[sample_id])
        review["grading"] = "clinical_review"
        assert grade(inputs[sample_id], review, good)["status"] == "REVIEW_REQUIRED"
        low = next(e for e in expected.values() if e["checks"].get("level_max") == 1)
        assert any(
            "above permitted" in f
            for f in grade(inputs[low["id"]], low, good)["failures"]
        )
        temporal_id = "TEMPORAL-ISOLATION.future-message"
        future = {
            "level": 1,
            "next_step": STEPS[1],
            "team_notification_required": False,
            "observations": {"chills": False},
            "evidence": [{"input_path": "/history/0/text"}],
            "used_event_ids": ["future"],
            "llm_requests": [{"text": inputs[temporal_id]["history"][0]["text"]}],
        }
        failures = grade(inputs[temporal_id], expected[temporal_id], future)["failures"]
        assert any("path points to a future" in f for f in failures)
        assert any("Future or unknown" in f for f in failures)
        assert any("leaked into an LLM" in f for f in failures)
        for allow_network in (False, True):
            with network_guard(allow_network):
                for transport in (smtplib.SMTP, smtplib.SMTP_SSL):
                    try:
                        transport("invalid.acceptance.example")
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("SMTP guard did not block transport")
                if not allow_network:
                    with socket.socket() as client:
                        try:
                            client.connect(("127.0.0.1", 9))
                        except RuntimeError:
                            pass
                        else:
                            raise AssertionError("Socket guard did not block transport")
        print(
            "Harness self-check passed: undertriage, overtriage, review status, future leakage and transport guards checked; application not evaluated"
        )
        return 0
    if not selected:
        parser.error("No matching cases")
    if args.command == "list":
        for e in selected:
            print(
                f"{e['id']} [{e['grading']}] "
                + "; ".join(f"{s['source_id']} {s['locator']}" for s in e["sources"])
            )
        return 0
    if not args.adapter or ":" not in args.adapter:
        parser.error(
            "--adapter module:function is required; this suite does not pretend to implement the future adapter"
        )
    module, name = args.adapter.split(":", 1)
    with network_guard(args.allow_network):
        adapter = getattr(importlib.import_module(module), name)
    results = []
    for e in selected:
        try:
            # Reference metadata and case IDs are never delivered to the adapter.
            raw = deepcopy(inputs[e["id"]])
            raw.pop("id")
            raw.setdefault("test_environment", {})["no_external_send"] = True
            with network_guard(args.allow_network):
                actual = adapter(raw)
            result = grade(inputs[e["id"]], e, actual)
        except Exception as exc:  # noqa: BLE001 -- isolate adapter failures without leaking secrets
            # Do not dump exception messages: an adapter could put API secrets
            # or an entire external response in them. Detailed local debugging
            # belongs in the adapter, outside a shareable acceptance report.
            result = {
                "status": "ERROR",
                "failures": [f"Adapter/contract error: {type(exc).__name__}"],
            }
        results.append(
            {"id": e["id"], "grading": e["grading"], "sources": e["sources"], **result}
        )
    report = {
        "suite": "MEDDI source-based acceptance/v1",
        "source_manifest": sources,
        "execution": {
            "adapter": args.adapter,
            "allow_network": args.allow_network,
            "tag": args.tag,
            "id_prefix": args.id,
            "grading": args.grading,
        },
        "source_sha256": {k: v["sha256"] for k, v in sources.items()},
        "counts": dict(Counter(r["status"] for r in results)),
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report["counts"], ensure_ascii=False))
    if any(r["status"] in {"FAIL", "ERROR"} for r in results):
        return 1
    return 3 if any(r["status"] == "REVIEW_REQUIRED" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
