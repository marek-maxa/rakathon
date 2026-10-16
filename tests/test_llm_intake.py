import json
from copy import deepcopy
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from llm_intake import Intake, load_question
from llm_intake.client import ASSETS, DEFAULT_DEPLOYMENT, APIError, Client
from llm_intake.core import validate


def extracted(value, evidence="Pomůže.", source_index=0):
    return {
        "status": "answered",
        "value": value,
        "source_index": source_index,
        "evidence": evidence,
        "follow_up": None,
    }


UNCLEAR = {
    "status": "unclear",
    "value": None,
    "source_index": None,
    "evidence": None,
    "follow_up": "Uleví se Vám od únavy, když si na chvíli sednete nebo lehnete?",
}


def test_reject_correct_and_confirm():
    question = load_question("nezadouci_ucinky", "unava")
    extractor = Mock(
        side_effect=[extracted(0), extracted(2, "Nepomůže ani při mytí.", 1)]
    )
    session = Intake(question, extractor)
    session.submit("Pomůže.")
    assert "Ano." in session.patient_summary()
    with pytest.raises(ValueError):
        session.confirmed_data()
    session.reject()
    with pytest.raises(ValueError):
        session.confirm()
    session.submit("Nepomůže ani při mytí.")
    result = session.confirm()
    assert result["odpoved_index"] == 2
    assert result["confirmed"] is True
    assert result["revision"] == 2
    assert "běžných denních činnostech" in session.patient_summary()
    assert extractor.call_args.args[1] == ["Pomůže.", "Nepomůže ani při mytí."]
    # Výstup je kopie; změna u volajícího nepřepíše potvrzený stav.
    result["source_messages"].clear()
    result["extraction"]["value"] = 0
    assert len(session.confirmed_data()["source_messages"]) == 2
    assert session.confirmed_data()["odpoved_index"] == 2
    with pytest.raises(ValueError):
        session.submit("Další změna bez nové relace")


def test_manual_answer_edit_is_validated_and_confirmed():
    session = Intake(
        load_question("nezadouci_ucinky", "pocit"),
        lambda *_: extracted(0, "Je mi dobře."),
    )
    session.submit("Je mi dobře.")
    result = session.confirm(4)

    assert result["odpoved_index"] == 4
    assert result["odpoved"] == "5 = velmi špatně"
    assert result["extraction"]["value"] == 4


def test_manual_answer_edit_rejects_invalid_values():
    session = Intake(
        load_question("nezadouci_ucinky", "pocit"),
        lambda *_: extracted(0, "Je mi dobře."),
    )
    session.submit("Je mi dobře.")

    with pytest.raises(ValueError, match="Extrahovaná hodnota"):
        session.confirm(5)
    assert session.state == "needs_confirmation"


def test_unclear_does_not_become_confirmed_or_negative():
    session = Intake(load_question("nezadouci_ucinky", "unava"), lambda *_: UNCLEAR)
    result = session.submit("Nevím, jsem unavená.")
    assert result["odpoved"] is None
    assert result["state"] == "needs_answer"
    with pytest.raises(ValueError):
        session.confirm()


def test_unclear_correction_does_not_reuse_rejected_value():
    extractor = Mock(side_effect=[extracted(0), UNCLEAR])
    session = Intake(load_question("nezadouci_ucinky", "unava"), extractor)
    session.submit("Pomůže.")
    session.reject()
    result = session.submit("Vlastně nevím.")
    assert result["odpoved"] is None
    assert result["revision"] == 2
    with pytest.raises(ValueError):
        session.confirm()


def test_targeted_clarifications_keep_question_answer_context():
    first_question = "Uleví se Vám, když odpočíváte i bez usnutí?"
    second_question = (
        "Omezuje Vás únava při běžných činnostech, nebo jen při větší námaze?"
    )
    extractor = Mock(
        side_effect=[
            {**UNCLEAR, "follow_up": first_question},
            {**UNCLEAR, "follow_up": second_question},
            extracted(1, "Jen při větší námaze.", 2),
        ]
    )
    question = load_question("nezadouci_ucinky", "unava")
    session = Intake(question, extractor)
    session.submit("ne, nejde mi spat")
    assert session.next_question == first_question
    assert session.patient_summary() == first_question
    session.submit("Ne, ani tak.")
    assert session.next_question == second_question
    session.submit("Jen při větší námaze.")
    assert session.state == "needs_confirmation"
    result = session.confirm()
    assert result["schema_version"] == 2
    assert result["odpoved_index"] == 1
    assert result["source_questions"] == [
        question.text,
        first_question,
        second_question,
    ]
    assert extractor.call_args.args[2] == result["source_questions"]
    assert result["metrics"]["clarifications_issued"] == 2
    assert result["metrics"]["successful_extractions"] == 3
    assert result["follow_up"] is None


def test_clarification_limit_stops_without_inventing_an_answer():
    extractor = Mock(
        side_effect=[
            UNCLEAR,
            {**UNCLEAR, "follow_up": "Jak Vás únava omezuje?"},
            UNCLEAR,
        ]
    )
    session = Intake(load_question("nezadouci_ucinky", "unava"), extractor)
    session.submit("Nevím.")
    session.submit("Pořád nevím.")
    result = session.submit("To neumím říct.")
    assert result["state"] == "unresolved"
    assert result["unresolved_reason"] == "clarification_limit"
    assert result["metrics"]["clarifications_issued"] == 2
    assert result["odpoved"] is None
    assert result["signaly_odpovedi"] == []
    assert result["confirmed"] is False
    with pytest.raises(ValueError):
        session.confirm()
    with pytest.raises(ValueError):
        session.submit("Znovu")
    assert extractor.call_count == 3


def test_repeated_original_question_is_not_asked_again():
    question = load_question("nezadouci_ucinky", "unava")
    session = Intake(question, lambda *_: {**UNCLEAR, "follow_up": question.text})
    result = session.submit("ne, nejde mi spat")
    assert result["state"] == "unresolved"
    assert result["unresolved_reason"] == "repeated_question"
    assert result["metrics"]["clarifications_issued"] == 0


@pytest.mark.parametrize(
    "follow_up", [None, "", "Upřesněte.", "Otázka? Další?", "A\nB?", "x" * 241 + "?"]
)
def test_unclear_requires_one_short_follow_up(follow_up):
    with pytest.raises(ValueError):
        validate(
            load_question("nezadouci_ucinky", "unava"),
            {**UNCLEAR, "follow_up": follow_up},
            ["Nevím."],
        )


def test_answered_result_cannot_trigger_unnecessary_follow_up():
    with pytest.raises(ValueError):
        validate(
            load_question("nezadouci_ucinky", "unava"),
            {**extracted(0), "follow_up": "Opravdu?"},
            ["Pomůže."],
        )


def test_cli_uses_follow_up_instead_of_repeating_original(monkeypatch, capsys):
    from llm_intake.__main__ import main

    follow_up = "Uleví se Vám od únavy i při odpočinku bez spaní?"
    client = Mock(
        side_effect=[{**UNCLEAR, "follow_up": follow_up}, extracted(0, "Ano.", 1)]
    )
    monkeypatch.setattr(Client, "from_env", lambda: client)
    monkeypatch.setattr("sys.argv", ["llm_intake"])
    answers = iter(["ne, nejde mi spat", "Ano.", "ano"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert main() == 0
    output = capsys.readouterr().out
    assert follow_up in output
    assert "Prosím odpověď upřesněte" not in output
    # Původní otázka je na začátku a pak v přehledu k potvrzení, ne při doptání.
    assert output.count(load_question("nezadouci_ucinky", "unava").text) == 2


@pytest.mark.parametrize("failure", [ValueError("invalid output"), APIError("timeout")])
def test_failed_correction_keeps_rejected_state(failure):
    extractor = Mock(side_effect=[extracted(0), failure])
    session = Intake(load_question("nezadouci_ucinky", "unava"), extractor)
    session.submit("Pomůže.")
    session.reject()
    before = session.snapshot()
    with pytest.raises(type(failure)):
        session.submit("Oprava: nepomůže.")
    assert session.snapshot() == before
    with pytest.raises(ValueError):
        session.confirmed_data()


@pytest.mark.parametrize(
    "result",
    [
        extracted(True),
        extracted(-1),
        extracted(3),
        extracted(0.0),
        extracted(0, "Vymyšlená citace"),
        extracted(0, source_index=True),
        extracted(0, source_index=1),
        {**extracted(0), "uroven": 1},
        {**UNCLEAR, "value": 0},
        {**extracted(0), "status": "confirmed"},
        [],
    ],
)
def test_invalid_extraction_never_updates_session(result):
    session = Intake(load_question("nezadouci_ucinky", "unava"), lambda *_: result)
    before = session.snapshot()
    with pytest.raises(ValueError):
        session.submit("Pomůže.")
    assert session.snapshot() == before


@pytest.mark.parametrize(
    "form,qid,value,valid",
    [
        ("bolest_analgeticka_terapie", "nu", [0, 1], True),
        ("bolest_analgeticka_terapie", "nu", [], True),
        ("bolest_analgeticka_terapie", "nu", [0, 0], False),
        ("bolest_analgeticka_terapie", "nu", [99], False),
        ("bolest_analgeticka_terapie", "nu", [[0]], False),
        ("psychoonkologicky_screening", "zvladani", 10, True),
        ("psychoonkologicky_screening", "zvladani", 0, False),
        ("psychoonkologicky_screening", "zvladani", "7", False),
        ("bolest_analgeticka_terapie", "sos", 2, True),
        ("bolest_analgeticka_terapie", "sos", -1, False),
        ("bolest_analgeticka_terapie", "sos", float("nan"), False),
        ("bolest_analgeticka_terapie", "sos", float("inf"), False),
        ("nezadouci_ucinky", "jine", "Svědění", True),
        ("nezadouci_ucinky", "jine", " ", False),
    ],
)
def test_question_value_types(form, qid, value, valid):
    question = load_question(form, qid)
    if valid:
        validate(question, extracted(value), ["Pomůže."])
    else:
        with pytest.raises(ValueError):
            validate(question, extracted(value), ["Pomůže."])


def test_examples_are_valid_and_have_original_evidence():
    for example in json.loads((ASSETS / "examples.json").read_text(encoding="utf-8")):
        spec = example["input"]["question"]
        question = load_question(spec["questionnaire_id"], spec["question_id"])
        validate(question, example["output"], example["input"]["source_messages"])


def test_cli_confirmation_and_correction(monkeypatch, capsys):
    from llm_intake.__main__ import main

    client = Mock(side_effect=[extracted(0), extracted(1, "Nepomůže při sportu.", 1)])
    client.model = "test-model"
    monkeypatch.setattr(Client, "from_env", lambda: client)
    monkeypatch.setattr("sys.argv", ["llm_intake", "--question", "unava", "--debug"])
    answers = iter(["Pomůže.", "ne", "Nepomůže při sportu.", "možná", "ano"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert main() == 0
    output = capsys.readouterr().out
    result = json.loads(output.split("Potvrzený JSON pro navazující modul:\n")[1])
    assert result["odpoved_index"] == 1
    assert result["confirmed"] is True
    assert client.call_count == 2


def test_payload_is_strict_and_excludes_triage():
    client = Client("test-secret")
    payload = client.payload(load_question("nezadouci_ucinky", "unava"), ["Pomůže."])
    assert payload["model"] == DEFAULT_DEPLOYMENT
    assert payload["response_format"]["json_schema"]["strict"] is True
    schema = payload["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == {
        "status",
        "value",
        "evidence",
        "source_index",
        "follow_up",
    }
    assert "test-secret" not in repr(client)


def test_api_adapter_uses_supplied_gateway_and_auth(monkeypatch):
    content = json.dumps(extracted(0))
    response = BytesIO(
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": content,
                        },
                    }
                ]
            }
        ).encode()
    )
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    result = Client("test-secret")(
        load_question("nezadouci_ucinky", "unava"), ["Pomůže."]
    )
    assert result["value"] == 0
    req = opener.open.call_args.args[0]
    assert req.full_url.endswith("/openai/v1/chat/completions")
    assert req.get_header("Api-key") == "test-secret"
    assert req.get_header("Authorization") is None
    assert json.loads(req.data)["messages"][-1]["role"] == "user"


@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "length", "message": {"content": "{}"}},
        {"finish_reason": "stop", "message": {"refusal": "no", "content": None}},
        {"finish_reason": "stop", "message": {"content": "not json"}},
    ],
)
def test_refusal_truncation_and_invalid_json_are_errors(monkeypatch, choice):
    opener = Mock()
    opener.open.return_value = BytesIO(json.dumps({"choices": [choice]}).encode())
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    with pytest.raises(APIError):
        Client("test-secret")(load_question("nezadouci_ucinky", "unava"), ["Pomůže."])


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError("https://example.invalid", 401, "unauthorized", {}, None),
        URLError("network unavailable"),
    ],
)
def test_transport_errors_do_not_include_secrets(monkeypatch, failure):
    opener = Mock()
    opener.open.side_effect = failure
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    with pytest.raises(APIError) as exc:
        Client("test-secret")(load_question("nezadouci_ucinky", "unava"), ["Pomůže."])
    assert "test-secret" not in str(exc.value)


def test_confirmation_cannot_be_injected_by_model():
    output = deepcopy(extracted(0))
    output["confirmed"] = True
    with pytest.raises(ValueError):
        validate(load_question("nezadouci_ucinky", "unava"), output, ["Pomůže."])


def test_patient_sees_question_then_only_matched_answer(monkeypatch, capsys):
    from llm_intake.__main__ import main

    question = load_question("nezadouci_ucinky", "unava")
    client = Mock(return_value=extracted(0))
    monkeypatch.setattr(Client, "from_env", lambda: client)
    monkeypatch.setattr("sys.argv", ["llm_intake", "--question", "unava"])
    calls = []

    def respond(_):
        output = capsys.readouterr().out
        calls.append(output)
        if len(calls) == 1:
            assert question.text in output
            assert all(option not in output for option in question.options)
            return "Pomůže."
        assert question.options[0] in output
        assert all(option not in output for option in question.options[1:])
        return "ano"

    monkeypatch.setattr("builtins.input", respond)
    assert main() == 0
    output = "".join(calls) + capsys.readouterr().out
    assert "Potvrzený JSON" not in output
    assert "signaly_odpovedi" not in output
    assert "zelena" not in output
    assert "cervena" not in output


def test_internal_signal_comes_from_definition_not_llm():
    question = load_question("nezadouci_ucinky", "pocit")
    assert all("barva" not in option for option in question.specification()["options"])
    session = Intake(question, lambda *_: extracted(4, "Je mi velmi špatně."))
    session.submit("Je mi velmi špatně.")
    confirmed = session.confirm()
    assert confirmed["signaly_odpovedi"] == [{"odpoved_index": 4, "barva": "cervena"}]
    assert "cervena" not in session.patient_summary()
    assert "uroven" not in confirmed


def test_unclear_answer_has_no_internal_signal():
    session = Intake(load_question("nezadouci_ucinky", "pocit"), lambda *_: UNCLEAR)
    assert session.submit("Nevím.")["signaly_odpovedi"] == []


@pytest.mark.parametrize(
    "header,expected_header,expected_value",
    [
        ("api-key", "Api-key", "test-secret"),
        ("Authorization", "Authorization", "Bearer test-secret"),
        ("Ocp-Apim-Subscription-Key", "Ocp-apim-subscription-key", "test-secret"),
    ],
)
def test_explicit_authentication_headers(
    monkeypatch, header, expected_header, expected_value
):
    opener = Mock()
    opener.open.return_value = BytesIO(
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(extracted(0))},
                    }
                ]
            }
        ).encode()
    )
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    Client("test-secret", key_header=header)(
        load_question("nezadouci_ucinky", "unava"), ["Pomůže."]
    )
    assert opener.open.call_args.args[0].get_header(expected_header) == expected_value


@pytest.mark.parametrize(
    "status,hint", [(401, "MEDDI_LLM_KEY_HEADER=api-key"), (404, "MEDDI_LLM_MODEL")]
)
def test_api_errors_point_to_auth_or_deployment(monkeypatch, status, hint):
    opener = Mock()
    opener.open.side_effect = HTTPError(
        "https://example.invalid", status, "error", {}, None
    )
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    with pytest.raises(APIError, match=hint):
        Client("test-secret")(load_question("nezadouci_ucinky", "unava"), ["Pomůže."])
