"""LLM packet -> time-bounded inputs -> the shared deterministic triage core.

No LLM calls, text interpretation, patient-card storage or clinical thresholds.
The caller supplies a CURRENT snapshot, not the patient's unrestricted history.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .clinical_rules import CONTEXT_FLAGS, OBSERVATION_FLAGS, OBSERVATION_NUMBERS
from .disposition import resolve_disposition
from .form import QUESTIONNAIRE_DEFINITIONS, prepare_checkin
from .triage import evaluate_checkin
from .validation import VITAL_FIELDS, number, prepared_inputs

NUMERIC_FACTS = {
    "temperature": "temperature_c",
    "temperature_c": "temperature_c",
    "oxygen": "spo2_pct",
    "spo2": "spo2_pct",
    "spo2_pct": "spo2_pct",
    "pain.nrs": "pain_nrs",
    "overall_feeling": "overall_feeling",
    **{name: name for name in OBSERVATION_NUMBERS},
}
FLAG_FACTS = {
    **{name: name for name in OBSERVATION_FLAGS},
    "breathlessness.at_rest": "breathlessness_at_rest",
    "suicidal_ideation": "suicidal_thoughts",
}
ANSWER_FIELDS = {
    ("nezadouci_ucinky", "teplota"): "temperature_c",
    ("nezadouci_ucinky", "pocit"): "overall_feeling",
    ("bolest_analgeticka_terapie", "nrs"): "pain_nrs",
    ("nezadouci_ucinky", "zvraceni"): "vomiting",
    ("nezadouci_ucinky", "prujem"): "diarrhea",
}
CURRENT_TEXT = {"dnes", "nyní", "nyni", "teď", "ted", "today", "now"}
ONGOING_ONSET = {
    "od včera",
    "od vcera",
    "od včerejška",
    "od vcerejska",
    "since yesterday",
}
DAY_WINDOW = {
    "za posledních 24 hodin",
    "za poslednich 24 hodin",
    "za 24 hodin",
    "za 24 h",
    "za 24h",
    "24 hodin",
    "24 h",
    "24h",
    "last 24 hours",
}
DURATION_UNITS = {
    "hours_without_diarrhea": r"h|hod|hodin[ay]?|hours?",
    "hours_without_urine": r"h|hod|hodin[ay]?|hours?",
    "nosebleed_minutes": r"min|minut[ay]?|minutes?",
    "constipation_days": r"den|dny|dní|dni|days?",
}


def _duration_text_matches(fact, text):
    unit = DURATION_UNITS.get(fact.get("concept"))
    if not unit or type(fact.get("value")) not in {int, float}:
        return False
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(?:" + unit + ")", text)
    return bool(match) and float(match[1].replace(",", ".")) == fact["value"]


def _instant(value):
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timestamps must contain a timezone")
    return parsed


def _slot(field):
    if field == "vomiting_episodes_24h":
        return "vomiting"
    if field == "stools_above_baseline_24h":
        return "diarrhea"
    return field


def _answer_candidate(item, index, root):
    q = item["question"]
    ref = (q["questionnaire_id"], q["question_id"])
    definition = next(
        (
            q
            for q in QUESTIONNAIRE_DEFINITIONS.get(ref[0], {}).get("otazky", [])
            if q["id"] == ref[1]
        ),
        None,
    )
    if definition is None:
        raise ValueError(f"Unknown question: {ref}")
    value = item.get("value")
    if value is None:
        raise ValueError("Confirmed answer requires a value")
    raw = {
        "otazka_id": ref[1],
        "odpoved": value,
        "odpoved_index": value if definition["typ"] in {"jedna", "vice"} else None,
    }
    prepared = prepare_checkin(
        {"dotazniky": [{"dotaznik_id": ref[0], "odpovedi": [raw]}]}
    )["answers"][0]
    turns = item.get("turns") or []
    evidence = item.get("evidence") or {}
    turn_index = evidence.get("turn_index")
    turn = (
        turns[turn_index]
        if type(turn_index) is int and 0 <= turn_index < len(turns)
        else (turns[-1] if turns else {})
    )
    source = {
        "kind": "answer",
        "answer_index": index,
        "evidence": deepcopy(evidence),
        "source_message_id": turn.get("source_message_id"),
        "confirmation": "confirmed",
    }
    stamp = turn.get("available_at") or root.get("available_at")
    return (
        ANSWER_FIELDS.get(ref, f"question:{ref[0]}/{ref[1]}"),
        value,
        source,
        stamp,
        item.get("observed_at"),
        prepared,
    )


def _select_current(candidates, issue):
    selected = []
    for field, entries in sorted(candidates.items()):
        if all(row["at"] is not None for row in entries):
            latest = max(row["at"] for row in entries)
            entries = [row for row in entries if row["at"] == latest]
        else:
            issue("unknown_observation_time", {"field": field})
        # A choice index is not a measurement: temperature choice 1 and 38.2 C
        # can agree. Compare like representations; the core checks their
        # clinical implications together (including conflicting fever reports).
        comparable = defaultdict(set)
        for row in entries:
            answer, value = row["answer"], row["value"]
            representation = ("field", row["field"])
            if answer is not None:
                ref = (answer["questionnaire_id"], answer["question_id"])
                if ref == ("nezadouci_ucinky", "pocit"):
                    value += 1
                elif ref != ("bolest_analgeticka_terapie", "nrs"):
                    representation = ("answer", *ref)
            comparable[representation].add(
                tuple(value) if isinstance(value, list) else value
            )
        if any(len(values) > 1 for values in comparable.values()):
            issue(
                "conflicting_current_values",
                {"field": field, "evidence": [r["source"] for r in entries]},
            )
        selected.extend(entries)
    return selected


def _prepare_inputs(root, treatment_sources, selected):
    prepared = prepare_checkin(
        {
            "patient_id": root.get("patient_id"),
            "checkin_id": root.get("id"),
            "stav": "vyplneno",
            "dotazniky": [],
        }
    )
    prepared["context_sources"] = treatment_sources
    observations = defaultdict(list)
    for row in selected:
        field, value, source = row["field"], row["value"], row["source"]
        if row["answer"] is not None:
            prepared["answers"].append(
                {**deepcopy(row["answer"]), "pipeline_source": source}
            )
        elif field in {"overall_feeling", "pain_nrs"}:
            ref = (
                ("nezadouci_ucinky", "pocit")
                if field == "overall_feeling"
                else ("bolest_analgeticka_terapie", "nrs")
            )
            value = value - 1 if field == "overall_feeling" else value
            answer = prepare_checkin(
                {
                    "dotazniky": [
                        {
                            "dotaznik_id": ref[0],
                            "odpovedi": [
                                {
                                    "otazka_id": ref[1],
                                    "odpoved": value,
                                    "odpoved_index": value
                                    if field == "overall_feeling"
                                    else None,
                                }
                            ],
                        }
                    ]
                }
            )["answers"][0]
            prepared["answers"].append({**answer, "pipeline_source": source})
        else:
            observations[field].append({"value": value, "source": source})
    # The flat fever/oxygen criteria also consume these two vital fields.
    # For simultaneous contradictions, preserve all reports in observations.
    prepared["vital_signs"] = {}
    for field, raw, select in (
        ("temperature_c", "teplota_c", max),
        ("spo2_pct", "spo2_pct", min),
    ):
        if observations.get(field):
            prepared["vital_signs"][raw] = {
                "hodnota": select(r["value"] for r in observations[field]),
                "source": deepcopy(observations[field]),
            }
    prepared["non_green_answers"] = [
        a for a in prepared["answers"] if a["color"] in {"yellow", "orange", "red"}
    ]
    return prepared, dict(observations)


def evaluate_contact(
    packet, patient_snapshot=None, *, context=None, now=None, prepared_checkin=None
):
    """Evaluate a packet from build_pipeline_packet/MasterDialogue, without mutation.

    patient_snapshot: {patient_id, as_of, context, observations}. Snapshot records
    may declare available_at, observed_at, valid_until and source. Its producer
    selects the current episode; no automatic clinical expiry is invented here.
    context is an explicitly current, normalized override/input (legacy callers).
    Missing metadata is visible and cannot produce a complete assessment.
    """
    if (
        packet.get("kind", "llm_intake") != "llm_intake"
        or packet.get("schema_version", 1) != 1
    ):
        raise ValueError("Expected an llm_intake pipeline packet, version 1")
    root = packet.get("message") or {}
    messages = packet.get("messages") or ([root] if root else [])
    by_id = {}
    for message in messages:
        if message["id"] in by_id:
            raise ValueError("Duplicate source message ID")
        if root.get("patient_id") and message.get("patient_id") != root["patient_id"]:
            raise ValueError("All messages must belong to the same patient")
        _instant(message.get("available_at"))
        by_id[message["id"]] = message
    moment = _instant(now)
    if moment is None:
        moment = max(
            (_instant(m["available_at"]) for m in messages if m.get("available_at")),
            default=None,
        )
    issues, unused, deferred = [], [], []
    candidates = defaultdict(list)

    def issue(code, source):
        issues.append({"code": code, "source": deepcopy(source)})

    def add(
        field,
        value,
        source,
        available=None,
        observed=None,
        answer=None,
        valid_until=None,
    ):
        available, observed = (
            _instant(available),
            _instant(observed) or _instant(available),
        )
        if observed and available and observed > available:
            raise ValueError("An observation cannot be known before it occurs")
        if moment and (
            (available and available > moment) or (observed and observed > moment)
        ):
            deferred.append({"reason": "future_input", "source": deepcopy(source)})
            return
        expiry = _instant(valid_until)
        if moment and expiry and expiry < moment:
            deferred.append({"reason": "expired_input", "source": deepcopy(source)})
            return
        source = {
            **deepcopy(source),
            "available_at": available.isoformat() if available else None,
            "observed_at": observed.isoformat() if observed else None,
        }
        candidates[_slot(field)].append(
            {
                "field": field,
                "value": value,
                "source": source,
                "at": observed,
                "answer": answer,
            }
        )

    snapshot = patient_snapshot or {}
    if set(snapshot) - {"patient_id", "as_of", "context", "observations"}:
        raise ValueError(
            "Expected a current patient snapshot, not unrestricted patient data"
        )
    if (
        snapshot.get("patient_id")
        and root.get("patient_id")
        and snapshot["patient_id"] != root["patient_id"]
    ):
        raise ValueError("Snapshot belongs to another patient")
    snapshot_at = _instant(snapshot.get("as_of"))
    if snapshot and snapshot_at is None:
        raise ValueError("Patient snapshot requires as_of with timezone")
    if snapshot and not snapshot.get("patient_id"):
        raise ValueError("Patient snapshot requires patient_id")
    if moment and snapshot_at and snapshot_at > moment:
        raise ValueError("Patient snapshot is not available at evaluation time")
    treatment, treatment_sources = {}, {}
    for source_kind, supplied, default_at in (
        ("snapshot", snapshot.get("context", {}), snapshot_at),
        ("snapshot", snapshot.get("observations", {}), snapshot_at),
        ("context", context or {}, moment),
    ):
        for field, raw in supplied.items():
            record = raw if isinstance(raw, dict) else {"value": raw}
            value = record.get("value")
            if value is None:
                continue
            available = _instant(record.get("available_at")) or default_at
            observed = _instant(record.get("observed_at")) or available
            source = {
                "kind": source_kind,
                "field": field,
                "source": deepcopy(record.get("source")),
            }
            if moment and available and available > moment:
                deferred.append({"reason": "future_input", "source": source})
                continue
            if observed and available and observed > available:
                raise ValueError("An observation cannot be known before it occurs")
            expiry = _instant(record.get("valid_until"))
            if moment and expiry and expiry < moment:
                deferred.append({"reason": "expired_input", "source": source})
                continue
            if field in CONTEXT_FLAGS | {
                "pain_persists_after_rescue_dose",
                "suicide_plan_intent_or_means",
            }:
                if type(value) is not bool:
                    raise ValueError(f"Context field {field} must be bool")
                # Current explicit context overrides a snapshot treatment flag.
                treatment[field] = value
                treatment_sources[field] = {
                    **source,
                    "available_at": available.isoformat() if available else None,
                }
            elif field in OBSERVATION_NUMBERS | {"pain_nrs", "overall_feeling"}:
                number(field, value, record.get("unit"))
                add(
                    field,
                    value,
                    source,
                    available,
                    observed,
                    valid_until=record.get("valid_until"),
                )
            elif field in OBSERVATION_FLAGS:
                if type(value) is not bool:
                    raise ValueError(f"Observation {field} must be bool")
                add(
                    field,
                    value,
                    source,
                    available,
                    observed,
                    valid_until=record.get("valid_until"),
                )
            else:
                raise ValueError(f"Unknown clinical input: {field}")

    if prepared_checkin is not None:
        prepared_inputs(prepared_checkin)
        if prepared_checkin.get("patient_id") != root.get("patient_id"):
            raise ValueError("Prepared check-in belongs to another patient")
        if prepared_checkin.get("checkin_id") != root.get("id"):
            raise ValueError("Prepared check-in belongs to another contact")
        for answer in prepared_checkin["answers"]:
            ref = (answer["questionnaire_id"], answer["question_id"])
            if answer["value"] is None and answer["option_indices"] is None:
                continue
            field = ANSWER_FIELDS.get(ref, f"question:{ref[0]}/{ref[1]}")
            add(
                field,
                answer["option_indices"]
                if answer["option_indices"] is not None
                else answer["value"],
                {"kind": "answer", "origin": "recorded_checkin", "question": ref},
                root["available_at"],
                answer=deepcopy(answer),
            )
        for raw, measurement in (prepared_checkin.get("vital_signs") or {}).items():
            if (
                raw in VITAL_FIELDS
                and measurement
                and measurement.get("hodnota") is not None
            ):
                add(
                    VITAL_FIELDS[raw],
                    measurement["hodnota"],
                    {
                        "kind": "measurement",
                        "field": raw,
                        "record": deepcopy(measurement),
                    },
                    root["available_at"],
                )

    for index, item in enumerate(packet.get("question_answers", [])):
        if not item.get("confirmed"):
            if item.get("state") not in {"skipped"}:
                issue("unconfirmed_answer", {"answer_index": index})
            continue
        if item.get("state", "confirmed") != "confirmed":
            raise ValueError("Confirmed answer has an inconsistent state")
        field, value, source, stamp, observed, prepared = _answer_candidate(
            item, index, root
        )
        add(field, value, source, stamp, observed, answer=prepared)

    for index, fact in enumerate(packet.get("facts", [])):
        source = {
            "kind": "fact",
            "fact_index": index,
            "source_message_id": fact.get("source_message_id"),
            "evidence": fact.get("evidence"),
            "confirmation": fact.get("confirmation", "unconfirmed"),
            "certainty": fact.get("certainty", "stated"),
        }
        message = by_id.get(fact.get("source_message_id")) or (
            root if not fact.get("source_message_id") else {}
        )
        if fact.get("source_message_id") and not message:
            unused.append({"reason": "unknown_source_message", "source": source})
            continue
        if message.get("text") is not None and (
            not fact.get("evidence") or fact["evidence"] not in message["text"]
        ):
            raise ValueError("Fact evidence is not in its source message")
        if (
            fact.get("time_text")
            and message.get("text") is not None
            and fact["time_text"] not in message["text"]
        ):
            raise ValueError("Fact time_text is not in its source message")
        available = message.get("available_at")
        if moment and available and _instant(available) > moment:
            deferred.append({"reason": "future_input", "source": source})
            continue
        concept = fact.get("concept")
        subject, presence = fact.get("subject"), fact.get("presence")
        if subject != "patient":
            if subject == "caregiver" and concept == "caregiver_exhaustion":
                pass
            else:
                unused.append({"reason": "other_or_unknown_subject", "source": source})
                continue
        if (
            presence not in {"present", "absent"}
            or fact.get("certainty") == "uncertain"
        ):
            unused.append({"reason": "uncertain_finding", "source": source})
            continue
        text = (fact.get("time_text") or "").strip().casefold().rstrip(".")
        if (
            text
            and text not in CURRENT_TEXT | DAY_WINDOW | ONGOING_ONSET
            and not _duration_text_matches(fact, text)
            and not fact.get("observed_at")
        ):
            unused.append({"reason": "unresolved_observation_time", "source": source})
            continue
        field = FLAG_FACTS.get(concept)
        if field:
            add(
                field, presence == "present", source, available, fact.get("observed_at")
            )
            continue
        field = NUMERIC_FACTS.get(concept)
        if concept in {
            "diarrhea.episodes",
            "diarrhea.increase_over_baseline",
            "vomiting.episodes",
        }:
            value = fact.get("value")
            positive = (type(value) in {int, float} and value > 0) or (
                isinstance(value, dict)
                and value.get("lower") is not None
                and (
                    value["lower"] > 0
                    or (value["lower"] == 0 and not value.get("lower_inclusive", True))
                )
            )
            if positive and presence == "present":
                # The count proves a symptom, never a 24 h window or a baseline.
                add(
                    "vomiting" if concept == "vomiting.episodes" else "diarrhea",
                    True,
                    source,
                    available,
                    fact.get("observed_at"),
                )
        if concept in {"vomiting.episodes", "diarrhea.increase_over_baseline"}:
            question = message.get("question") or ""
            if text in DAY_WINDOW or (
                concept == "vomiting.episodes"
                and message.get("source") == "targeted_answer"
                and question
                == next(
                    q["text"]
                    for q in QUESTIONNAIRE_DEFINITIONS["nezadouci_ucinky"]["otazky"]
                    if q["id"] == "zvraceni"
                )
            ):
                field = (
                    "vomiting_episodes_24h"
                    if concept == "vomiting.episodes"
                    else "stools_above_baseline_24h"
                )
            else:
                unused.append({"reason": "missing_24h_window", "source": source})
                continue
        if (
            field is None
            or presence == "absent"
            or fact.get("value") is None
            or isinstance(fact.get("value"), (dict, str))
        ):
            unused.append(
                {"reason": "unsupported_or_nonexact_finding", "source": source}
            )
            continue
        if field in {"vomiting_episodes_24h", "stools_above_baseline_24h"} and fact.get(
            "unit"
        ) not in {None, "episodes", "stools", "episodes/24h", "stools/24h"}:
            raise ValueError("Count requires episodes/stools, not another unit")
        number(field, fact["value"], fact.get("unit"))
        add(field, fact["value"], source, available, fact.get("observed_at"))

    selected = _select_current(candidates, issue)
    prepared, observations = _prepare_inputs(root, treatment_sources, selected)
    if prepared_checkin is not None:
        prepared["answers"].extend(
            deepcopy(a)
            for a in prepared_checkin["answers"]
            if a["value"] is None and a["option_indices"] is None
        )
        for name, value in prepared_checkin.items():
            if name not in {
                "answers",
                "non_green_answers",
                "vital_signs",
                "context_sources",
            }:
                prepared[name] = deepcopy(value)
        for raw, measurement in (prepared_checkin.get("vital_signs") or {}).items():
            prepared["vital_signs"].setdefault(raw, deepcopy(measurement))
    result = evaluate_checkin(prepared, treatment, dict(observations))
    dialog_state = (packet.get("dialogue") or {}).get("state")
    if dialog_state and dialog_state != "complete":
        issue("intake_not_complete", {"state": dialog_state})
    if not root.get("id") or not root.get("patient_id") or not moment:
        issue("missing_contact_metadata", {})
    incomplete = bool(
        result["requires_review"]
        or issues
        or unused
        or deferred
        or packet.get("unmapped_concepts")
        or packet.get("unknown_subject_fact_indices")
    )
    return resolve_disposition(
        {
            **result,
            "kind": "meddi_contact_assessment",
            "schema_version": 1,
            "evaluated_at": moment.isoformat() if moment else None,
            "assessment_status": "incomplete" if incomplete else "complete",
            "requires_review": incomplete,
            "adapter_issues": issues,
            "unprocessed_facts": unused,
            "deferred_inputs": deferred,
            "triage_inputs": {
                "prepared": prepared,
                "context": treatment,
                "observations": dict(observations),
            },
            "intake": deepcopy(packet),
        },
        needs_clinical_review=bool(
            result["needs_clinical_review"]
            or issues
            or unused
            or packet.get("unmapped_concepts")
            or packet.get("unknown_subject_fact_indices")
        ),
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="LLM packet -> shared backend triage (no LLM calls)"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--at", help="Evaluation time including timezone")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig")) if path else None

    result = evaluate_contact(
        read(args.input), read(args.snapshot), context=read(args.context), now=args.at
    )
    text = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
