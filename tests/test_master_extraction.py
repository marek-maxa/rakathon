"""Kontrola schématu, zdrojů a směrování; model a síť se zde nahrazují."""

import json
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO
from unittest.mock import Mock

import pytest

from llm_intake.client import ASSETS, APIError, Client
from llm_intake.master import (
    MasterExtractor,
    analyze_message,
    load_schema,
    main,
    validate_facts,
)
from llm_intake.master_contract import Fact, MessageEvent, NumericRange

EXAMPLES = json.loads((ASSETS / "master_examples.json").read_text(encoding="utf-8"))


def response(example=0):
    return {
        "facts": [asdict(Fact.from_dict(fact)) for fact in EXAMPLES[example]["facts"]]
    }


def event(example=0):
    return MessageEvent(**EXAMPLES[example]["message"])


@pytest.mark.parametrize(
    "index,question_ids,unmapped",
    [
        (0, ["zvraceni", "unava"], []),
        (1, [], ["sleep_difficulty"]),
        (2, ["prujem"], []),
        (3, ["zvraceni"], []),
        (4, [], ["overall_feeling", "pain.nrs"]),
    ],
)
def test_examples_route_only_patient_findings_and_keep_all_facts(
    index, question_ids, unmapped
):
    original = response(index)
    facts = validate_facts(original, event(index))
    packet = analyze_message(event(index), lambda _: facts)
    assert len(packet["facts"]) == len(original["facts"])
    assert [
        c["question"]["question_id"] for c in packet["question_candidates"]
    ] == question_ids
    assert packet["unmapped_concepts"] == unmapped
    assert packet["question_answers"] == []
    assert all(fact["confirmation"] == "unconfirmed" for fact in packet["facts"])
    assert response(index) == original
    assert json.loads(json.dumps(packet, allow_nan=False)) == packet


def test_range_and_approximation_are_not_replaced_by_worse_exact_value():
    facts = validate_facts(response(), event())
    assert facts[0].value == NumericRange(5, 6)
    assert facts[0].certainty == "uncertain"
    fact = validate_facts(response(2), event(2))[0]
    assert fact.value == 6 and fact.certainty == "approximate"
    assert fact.time_text == "Od včera"
    assert fact.concept == "diarrhea.episodes"


def test_unknown_subject_is_retained_without_asking_patient_about_it():
    fact = Fact("fatigue", "present", "unavený", "unknown")
    packet = analyze_message(event(), lambda _: [fact])
    assert packet["facts"][0]["subject"] == "unknown"
    assert packet["unknown_subject_fact_indices"] == [0]
    assert packet["question_candidates"] == []


def test_uncertain_presence_remains_uncertain_and_can_prompt_clarification():
    message = MessageEvent(
        "synthetic-uncertain",
        "synthetic-patient",
        "Nevím, zda mám teplotu.",
        "2026-10-16T10:00:00+02:00",
        "patient_message",
        "patient",
    )
    fact = Fact(
        "temperature", "uncertain", message.text, "patient", certainty="uncertain"
    )
    packet = analyze_message(message, lambda _: [fact])
    assert packet["facts"][0]["presence"] == "uncertain"
    assert packet["question_candidates"][0]["question"]["question_id"] == "teplota"
    assert packet["question_candidates"][0]["fact_indices"] == [0]


def test_multiple_facts_deduplicate_question_and_keep_both_reasons():
    message = event()
    facts = [
        Fact("vomiting", "present", "zvracel", "patient"),
        Fact(
            "vomiting.episodes",
            "present",
            "zvracel pětkrát nebo šestkrát",
            "patient",
            NumericRange(5, 6),
        ),
    ]
    packet = analyze_message(message, lambda _: facts)
    assert len(packet["question_candidates"]) == 1
    assert packet["question_candidates"][0]["fact_indices"] == [0, 1]


def test_empty_extraction_is_not_a_normal_health_assessment():
    packet = analyze_message(event(), lambda _: [])
    assert packet["analysis_status"] == "no_facts"
    assert packet["question_candidates"] == []
    assert "color" not in packet and "severity" not in packet


@pytest.mark.parametrize(
    "result", [[], None, {}, {"facts": None}, {"facts": [], "severity": "green"}]
)
def test_invalid_envelope_is_rejected(result):
    with pytest.raises(ValueError):
        validate_facts(result, event())


@pytest.mark.parametrize(
    "changes",
    [
        {"confirmation": "confirmed"},
        {"presence": "maybe"},
        {"subject": ["patient"]},
        {"value": True},
        {"value": float("nan")},
        {"value": " "},
        {"value": {"lower": 5, "upper": 6}},
        {"concept": "nevolnost / zvraceni"},
        {"evidence": "pacient má horečku"},
        {"time_text": "včera"},
        {"presence": "absent", "value": 36.6},
    ],
)
def test_invalid_or_fabricated_fact_rejects_whole_response(changes):
    result = response()
    result["facts"][1].update(changes)
    with pytest.raises(ValueError):
        validate_facts(result, event())


def test_missing_required_field_is_not_silently_defaulted():
    result = response()
    del result["facts"][0]["certainty"]
    with pytest.raises(ValueError):
        validate_facts(result, event())


def test_schema_is_strict_at_every_object_level():
    def visit(schema):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
        for value in schema.values():
            if isinstance(value, dict):
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        visit(item)

    visit(load_schema())


def test_payload_keeps_actual_question_and_packages_without_patient_metadata():
    message = MessageEvent(
        "private-message-id",
        "private-patient-id",
        "Dnes nezvracím.",
        "2026-10-16T10:00:00+02:00",
        "targeted_answer",
        "patient",
        "Zvracel jste dnes?",
    )
    payload = MasterExtractor(Client("test-secret")).payload(message)
    assert "test-secret" not in json.dumps(payload)
    assert "private-patient-id" not in json.dumps(payload)
    assert "private-message-id" not in json.dumps(payload)
    actual = json.loads(payload["messages"][-1]["content"])
    assert actual["message"]["question"] == "Zvracel jste dnes?"
    assert set(actual["message"]) == {"text", "question", "author"}
    guide = actual["concept_guide"]
    assert set(guide) == {
        "vomiting",
        "diarrhea",
        "fatigue",
        "temperature",
        "breathlessness",
        "bleeding",
    }
    assert guide["vomiting"][0]["options"]
    assert "barva" not in json.dumps(guide)
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"] == load_schema()
    for example in payload["messages"][2:-1:2]:
        assert set(json.loads(example["content"])) == {"facts"}


def test_extractor_uses_existing_transport_and_locally_validates(monkeypatch):
    opener = Mock()
    opener.open.return_value = BytesIO(
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(response())},
                    }
                ]
            }
        ).encode()
    )
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    facts = MasterExtractor(Client("test-secret"))(event())
    assert facts[0].value == NumericRange(5, 6)
    req = opener.open.call_args.args[0]
    assert req.get_header("Api-key") == "test-secret"
    assert (
        json.loads(req.data)["response_format"]["json_schema"]["name"]
        == "patient_message_facts"
    )


def test_api_failure_does_not_become_empty_success(monkeypatch):
    def fail(*_):
        raise APIError("Simulovaný výpadek.")

    monkeypatch.setattr(Client, "send", fail)
    with pytest.raises(APIError):
        analyze_message(event(), MasterExtractor(Client("test-secret")))


def test_cli_json_is_ready_for_pipeline_without_confirmed_answers(
    monkeypatch, tmp_path, capsys
):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(EXAMPLES[3]["message"]), encoding="utf-8-sig")
    original = deepcopy(EXAMPLES[3])
    monkeypatch.setattr("sys.argv", ["master", str(path)])
    monkeypatch.setattr(Client, "from_env", lambda: Client("test-secret"))
    monkeypatch.setattr(Client, "send", lambda *_: response(3))
    assert main() == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["message"]["author"] == "caregiver"
    assert [c["question"]["question_id"] for c in packet["question_candidates"]] == [
        "zvraceni"
    ]
    assert EXAMPLES[3] == original


def test_cli_api_error_emits_no_success_packet(monkeypatch, tmp_path, capsys):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(EXAMPLES[0]["message"]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["master", str(path)])
    monkeypatch.setattr(Client, "from_env", lambda: Client("test-secret"))

    def fail(*_):
        raise APIError("Simulovaný výpadek.")

    monkeypatch.setattr(Client, "send", fail)
    assert main() == 1
    output = capsys.readouterr()
    assert output.out == "" and "Chyba:" in output.err
    assert "test-secret" not in output.err
