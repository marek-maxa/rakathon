"""Samostatný kontrakt před LLM: zdroje, nejistota a dohledatelné vazby."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from llm_intake.master_contract import Fact, MessageEvent, NumericRange, build_packet
from llm_intake.question_catalog import load_catalog, lookup_questions

EXAMPLES = json.loads(
    (Path(__file__).parents[1] / "llm_intake" / "master_examples.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("example", EXAMPLES, ids=[case["name"] for case in EXAMPLES])
def test_synthetic_contract_examples(example):
    original = deepcopy(example)
    packet = build_packet(
        MessageEvent(**example["message"]),
        [Fact.from_dict(data) for data in example["facts"]],
    )
    assert example == original
    assert json.loads(json.dumps(packet)) == packet
    assert packet["message"]["text"] == example["message"]["text"]
    assert all(fact["confirmation"] == "unconfirmed" for fact in packet["facts"])
    assert all(
        fact["source_message_id"] == example["message"]["id"]
        for fact in packet["facts"]
    )


def message(**overrides):
    return MessageEvent(
        **{
            "id": "synthetic-message",
            "patient_id": "synthetic-patient",
            "text": "Včera jsem asi šestkrát zvracel.",
            "available_at": "2026-10-16T10:00:00+02:00",
            "source": "patient_message",
            "author": "patient",
            **overrides,
        }
    )


def test_no_unmentioned_findings_or_invented_exact_time():
    packet = build_packet(message(), [])
    assert packet["facts"] == []
    packet = build_packet(
        message(),
        [
            Fact(
                "vomiting.episodes",
                "present",
                "asi šestkrát zvracel",
                "patient",
                6,
                "episodes",
                "Včera",
                "approximate",
            )
        ],
    )
    fact = packet["facts"][0]
    assert fact["time_text"] == "Včera"
    assert fact["certainty"] == "approximate"
    assert "observed_at" not in fact
    assert "severity" not in fact


@pytest.mark.parametrize(
    "kwargs",
    [
        {"evidence": "nezvracím"},
        {"evidence": "zvracel", "time_text": "za posledních 24 hodin"},
    ],
)
def test_fabricated_source_or_time_rejected(kwargs):
    with pytest.raises(ValueError):
        build_packet(
            message(), [Fact("vomiting", "present", subject="patient", **kwargs)]
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"available_at": "2026-10-16T10:00:00"},
        {"source": "master_question"},
        {"source": "targeted_answer", "question": ""},
        {"author": "model"},
    ],
)
def test_event_requires_known_metadata_and_actual_question(overrides):
    with pytest.raises(ValueError):
        message(**overrides)


@pytest.mark.parametrize(
    "bounds",
    [
        {"lower": None, "upper": None},
        {"lower": 6, "upper": 5},
        {"lower": 5, "upper": 5, "upper_inclusive": False},
        {"lower": True, "upper": 5},
        {"lower": 5, "upper": float("nan")},
    ],
)
def test_invalid_numeric_ranges_rejected(bounds):
    with pytest.raises(ValueError):
        NumericRange(**bounds)


def test_open_range_is_not_rounded_to_a_worse_exact_value():
    fact = Fact.from_dict(
        {
            "concept": "vomiting.episodes",
            "presence": "present",
            "subject": "patient",
            "evidence": "zvracel",
            "value": {"lower": 5, "upper": None, "lower_inclusive": False},
        }
    )
    packet = build_packet(message(), [fact])
    assert packet["facts"][0]["value"] == {
        "lower": 5,
        "upper": None,
        "lower_inclusive": False,
        "upper_inclusive": True,
    }


@pytest.mark.parametrize("value", [False, float("inf"), [5, 6]])
def test_invalid_measurements_rejected(value):
    with pytest.raises(ValueError):
        Fact("vomiting.episodes", "present", "zvracel", "patient", value=value)


def test_negation_is_not_a_fabricated_measurement():
    with pytest.raises(ValueError):
        Fact("temperature", "absent", "Nemám horečku", "patient", value=36.6)


def test_author_and_subject_are_independent():
    case = EXAMPLES[3]
    packet = build_packet(
        MessageEvent(**case["message"]),
        [Fact.from_dict(fact) for fact in case["facts"]],
    )
    assert packet["message"]["author"] == "caregiver"
    assert [fact["subject"] for fact in packet["facts"]] == ["patient", "caregiver"]


def test_model_cannot_confirm_a_fact():
    with pytest.raises(TypeError):
        Fact.from_dict(
            {
                "concept": "vomiting",
                "presence": "present",
                "evidence": "zvracel",
                "subject": "patient",
                "confirmation": "confirmed",
            }
        )


def test_catalog_keeps_questionnaire_identity_and_branch_condition():
    catalog = load_catalog()
    assert len(catalog) == 49
    fatigue_refs = [ref for ref in catalog if ref[1] == "unava"]
    assert len(fatigue_refs) == 2
    assert catalog[("nezadouci_ucinky", "zvraceni")]["condition"] is not None


def test_lookup_keeps_unmapped_concepts_and_deduplicates_related_questions():
    result = lookup_questions(
        [
            "vomiting",
            "vomiting.episodes",
            "sleep_difficulty",
            "sleep_difficulty",
            "bleeding",
        ]
    )
    assert [(q["questionnaire_id"], q["question_id"]) for q in result["questions"]] == [
        ("nezadouci_ucinky", "zvraceni"),
        ("nezadouci_ucinky", "krvaceni"),
        ("nezadouci_ucinky", "krvaceni_popis"),
    ]
    assert result["unmapped_concepts"] == ["sleep_difficulty"]


def test_unmapped_facts_remain_in_packet():
    case = EXAMPLES[4]
    packet = build_packet(
        MessageEvent(**case["message"]),
        [Fact.from_dict(fact) for fact in case["facts"]],
    )
    assert packet["facts"][1]["value"] == 0
    assert lookup_questions(fact["concept"] for fact in packet["facts"])[
        "unmapped_concepts"
    ] == [
        "overall_feeling",
        "pain.nrs",
    ]
