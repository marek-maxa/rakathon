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
