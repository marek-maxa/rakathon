from unittest.mock import Mock

import pytest

from llm_intake import Intake, load_question
from llm_intake.client import Client
from tests.test_llm_intake import extracted
from triage import evaluate_intake


@pytest.mark.parametrize(
    "form, question, value, color",
    [
        ("nezadouci_ucinky", "pocit", 4, "orange"),
        ("nezadouci_ucinky", "pocit", 0, None),
        ("bolest_analgeticka_terapie", "nrs", 5, "yellow"),
        ("bolest_analgeticka_terapie", "nrs", 8, None),
        ("nezadouci_ucinky", "unava", 0, None),
    ],
)
def test_confirmed_answer_mapping(form, question, value, color):
    session = Intake(load_question(form, question), Mock(return_value=extracted(value)))
    session.submit("Pomůže.")
    assert evaluate_intake(session.snapshot())["color"] is None
    result = evaluate_intake(session.confirm())
    assert result["color"] == color
    assert result["requires_review"]  # One answer cannot complete the assessment.


def test_cli_prints_triage_after_confirmation(monkeypatch, capsys):
    from llm_intake.__main__ import main

    client = Mock(return_value=extracted(4, "Velmi špatně."))
    client.model = "test-model"
    monkeypatch.setattr(Client, "from_env", lambda: client)
    monkeypatch.setattr("sys.argv", ["llm_intake", "--question", "pocit"])
    answers = iter(["Velmi špatně.", "ano"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert main() == 0
    output = capsys.readouterr().out
    assert "omezená sada pravidel): orange" in output
    assert "Posouzení je neúplné" in output


def test_evaluate_pipeline_packet_maps_feeling_and_pain():
    from triage import evaluate_pipeline_packet

    packet = {
        "kind": "llm_intake",
        "question_answers": [
            {
                "question": {
                    "questionnaire_id": "nezadouci_ucinky",
                    "question_id": "pocit",
                },
                "confirmed": True,
                "value": 4,  # overall_feeling = 5
            }
        ],
        "facts": [],
    }
    result = evaluate_pipeline_packet(packet)
    assert result["color"] == "orange"
    assert result["scores"]["overall_feeling"] == 3
    assert result["requires_review"] is True


def test_evaluate_pipeline_packet_with_fever_and_chemo_context():
    from triage import evaluate_intake, evaluate_pipeline_packet

    packet = {
        "kind": "llm_intake",
        "question_answers": [],
        "facts": [
            {
                "concept": "temperature",
                "presence": "present",
                "subject": "patient",
                "value": 38.5,
            }
        ],
    }
    # Bez kontextu chemoterapie zůstává horečka k posouzení
    assert evaluate_pipeline_packet(packet)["color"] is None

    # S kontextem chemoterapie je to červená úroveň
    result = evaluate_intake(packet, context={"chemotherapy_within_6_weeks": True})
    assert result["color"] == "red"
    assert result["scores"]["fever"] == 4


def test_pipeline_duration_is_not_a_temperature_measurement():
    from triage import evaluate_pipeline_packet

    packet = {
        "facts": [
            {
                "concept": "temperature.duration",
                "subject": "patient",
                "presence": "present",
                "value": 40,
                "unit": "hours",
            }
        ]
    }
    result = evaluate_pipeline_packet(packet, {"chemotherapy_within_6_weeks": True})
    assert result["color"] is None
    assert result["scores"]["fever"] is None


@pytest.mark.parametrize(
    "value,unit",
    [(True, "C"), (float("nan"), "C"), (float("inf"), "C"), (40, "hours"), (-1, "C")],
)
def test_pipeline_rejects_invalid_temperature_measurements(value, unit):
    from triage import evaluate_pipeline_packet

    packet = {
        "facts": [
            {
                "concept": "temperature",
                "subject": "patient",
                "presence": "present",
                "value": value,
                "unit": unit,
            }
        ]
    }
    with pytest.raises(ValueError):
        evaluate_pipeline_packet(packet)


@pytest.mark.parametrize("value,unit", [(101, "%"), (0.9, "fraction")])
def test_pipeline_rejects_invalid_oxygen_measurements(value, unit):
    from triage import evaluate_pipeline_packet

    packet = {
        "facts": [
            {
                "concept": "spo2",
                "subject": "patient",
                "presence": "present",
                "value": value,
                "unit": unit,
            }
        ]
    }
    with pytest.raises(ValueError):
        evaluate_pipeline_packet(packet)
