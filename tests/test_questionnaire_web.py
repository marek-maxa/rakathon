"""Complete real questionnaire definitions; synthetic answers and no network."""

import json
from base64 import b64encode
from copy import deepcopy

import pytest

from llm_intake.client import APIError
from llm_intake.core import load_questions
from llm_intake.master_contract import Fact
from web.app import app, sessions


@pytest.fixture
def browser(monkeypatch, tmp_path):
    patient = {
        "patient_id": "synthetic",
        "demografie": {"jmeno_fiktivni": "Synthetic Patient"},
        "lecba": {},
        "checkiny": [],
    }
    monkeypatch.setattr("web.app.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.app.load_patient", lambda _: deepcopy(patient))
    monkeypatch.setattr(
        "web.patient_store.load_source_patient", lambda _: deepcopy(patient)
    )
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "demo")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "synthetic-password")
    monkeypatch.setitem(app.config, "DATA_DIR", tmp_path)
    monkeypatch.setitem(app.config, "TESTING", True)
    answer_calls, message_calls = [], []

    class SyntheticClient:
        def extract_events(self, question, sources, questions, events):
            answer_calls.append((question.id, deepcopy(events)))
            return {
                "status": "answered",
                "value": json.loads(sources[-1]),
                "source_index": len(sources) - 1,
                "evidence": sources[-1],
                "follow_up": None,
            }

    def extract_message(message):
        message_calls.append(message)
        if message.source == "patient_message":
            return [Fact("confusion", "present", message.text, "patient")]
        return []

    monkeypatch.setattr("web.app.Client.from_env", lambda: SyntheticClient())
    monkeypatch.setattr("web.app.MasterExtractor", lambda _: extract_message)
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Basic " + b64encode(
        b"demo:synthetic-password"
    ).decode("ascii")
    client.post("/", data={"patient_id": "synthetic"})
    with client.session_transaction() as flask_session:
        key = flask_session["id"]
    yield client, key, tmp_path, answer_calls, message_calls
    sessions.pop(key, None)


def select_form(client, form="nezadouci_ucinky"):
    response = client.post("/", data={"questionnaire_id": form}, follow_redirects=True)
    assert response.status_code == 200
    assert "Závěrečná zpráva (nepovinná)" not in response.get_data(as_text=True)


def answer_form(client, key, *, all_branches=False):
    visited = []
    while sessions[key]["contact"].state == "needs_answer":
        assert len(visited) < 50
        question = sessions[key]["contact"].active.question
        visited.append(question.id)
        if question.id == "ucinky":
            value = list(range(12)) if all_branches else [12]
        elif all_branches and question.id in {"nnz_typ", "bolesti_typ", "stolice_typ"}:
            value = list(range(len(question.options)))
        elif all_branches and question.id == "krvaceni":
            value = 1
        elif all_branches and question.id == "nu":
            value = [3]
        else:
            value = (
                [0]
                if question.kind == "vice"
                else 1
                if question.kind == "skala_1_10"
                else "synthetic description"
                if question.kind == "text"
                else 0
            )
        response = client.post(
            "/", data={"answer": json.dumps(value)}, follow_redirects=True
        )
        assert response.status_code == 200
        assert "Odeslání se nezdařilo" not in response.get_data(as_text=True)
    assert sessions[key]["contact"].state == "needs_message"
    return visited


@pytest.mark.parametrize(
    "form", list(dict.fromkeys(q.questionnaire_id for q in load_questions()))
)
def test_complete_selected_form_then_skip_and_save(browser, form):
    client, key, directory, answer_calls, message_calls = browser
    html = client.get("/").get_data(as_text=True)
    assert 'value="nezadouci_ucinky" selected' in html
    select_form(client, form)
    assert (
        not answer_calls and not message_calls
    )  # Selecting a form makes no API request.
    visited = answer_form(client, key, all_branches=True)
    expected = [q.id for q in load_questions() if q.questionnaire_id == form]
    assert visited == expected
    assert [q for q, _ in answer_calls] == expected
    assert not list(directory.rglob("*.json"))
    call_count = len(message_calls)
    response = client.post("/", data={"skip_message": "1"}, follow_redirects=True)
    assert "Zkontrolujte všechny odpovědi" in response.get_data(as_text=True)
    assert len(message_calls) == call_count
    packet = sessions[key]["contact"].snapshot()
    assert packet["dialogue"]["state"] == "complete"
    assert packet["dialogue"]["patient_message_status"] == "skipped"
    assert all(event["source"] == "targeted_answer" for event in packet["messages"])
    assert all(not answer["confirmed"] for answer in packet["question_answers"])
    response = client.post("/", data={"confirm": "1"}, follow_redirects=True)
    assert "Odpovědi jsou uložené." in response.get_data(as_text=True)
    checkin = json.loads(
        (directory / "pacienti/synthetic.json").read_text(encoding="utf-8")
    )["checkiny"][-1]
    assert [row["dotaznik_id"] for row in checkin["dotazniky"]] == [form]
    assert checkin["zprava_pacienta"] == ""


def test_message_after_negative_questionnaire_changes_triage_without_opening_other_forms(
    browser,
):
    client, key, directory, answer_calls, message_calls = browser
    select_form(client)
    assert answer_form(client, key) == ["pocit", "sobestacnost", "ucinky"]
    before_answers = len(answer_calls)
    response = client.post(
        "/", data={"patient_message": "Jsem zmatený."}, follow_redirects=True
    )
    assert "Vaše zpráva: Jsem zmatený." in response.get_data(as_text=True)
    assert len(answer_calls) == before_answers
    assert message_calls[-1].source == "patient_message"
    assert sessions[key]["assessment"]["color"] == "red"
    packet = sessions[key]["contact"].snapshot()
    assert packet["facts"][0]["evidence"] == "Jsem zmatený."
    assert packet["dialogue"]["patient_message_status"] == "submitted"
    assert len(packet["dialogue"]["flows"]) == 1
    assert (
        "Jsem zmatený." not in packet["message"]["text"]
    )  # Actual first answer anchors the contact.
    client.post("/", data={"confirm": "1"})
    checkin = json.loads(
        (directory / "pacienti/synthetic.json").read_text(encoding="utf-8")
    )["checkiny"][-1]
    assert checkin["zprava_pacienta"] == "Jsem zmatený."
    assert checkin["triage_assessment"]["color"] == "red"
    assert (
        checkin["triage_assessment"]["intake"]["messages"][-1]["text"]
        == "Jsem zmatený."
    )


@pytest.mark.parametrize(
    "action",
    [{"skip_message": "1"}, {"patient_message": ""}, {"patient_message": "   "}],
)
def test_empty_or_skipped_message_does_not_call_model(browser, action):
    client, key, _, _, message_calls = browser
    select_form(client)
    answer_form(client, key)
    before = len(message_calls)
    response = client.post("/", data=action, follow_redirects=True)
    assert "Zpráva pacienta byla přeskočena." in response.get_data(as_text=True)
    assert len(message_calls) == before
    before_packet = sessions[key]["contact"].snapshot()
    client.post("/", data={"patient_message": "late duplicate"})
    assert sessions[key]["contact"].snapshot() == before_packet
    assert len(message_calls) == before


def test_message_error_preserves_form_and_text_for_retry(browser, monkeypatch):
    client, key, directory, _, _ = browser
    select_form(client)
    answer_form(client, key)
    before = sessions[key]["contact"].snapshot()

    def fail(_):
        raise APIError("synthetic model failure")

    with monkeypatch.context() as patch:
        patch.setattr(sessions[key]["contact"], "_extract_message", fail)
        response = client.post("/", data={"patient_message": "Jsem zmatený."})
    html = response.get_data(as_text=True)
    assert "synthetic model failure" in html
    assert ">Jsem zmatený.</textarea>" in html
    assert sessions[key]["contact"].snapshot() == before
    assert not list(directory.rglob("*.json"))
    assert (
        client.post("/", data={"patient_message": "Jsem zmatený."}).status_code == 302
    )


def test_message_and_confirmation_cannot_bypass_unanswered_form(browser):
    client, key, _, _, message_calls = browser
    response = client.post("/", data={"questionnaire_id": "invalid"})
    assert "Vyberte platný dotazník." in response.get_data(as_text=True)
    assert sessions[key]["contact"] is None
    select_form(client)
    for action in (
        {"patient_message": "Jsem zmatený."},
        {"skip_message": "1"},
        {"confirm": "1"},
    ):
        response = client.post("/", data=action)
        assert "Odeslání se nezdařilo" in response.get_data(as_text=True)
    assert not message_calls
    assert sessions[key]["contact"].active.question.id == "pocit"


def test_editing_parent_removes_conditional_answers_and_keeps_final_message(browser):
    client, key, _, _, _ = browser
    select_form(client)
    answer_form(client, key, all_branches=True)
    client.post("/", data={"patient_message": "Jsem zmatený."})
    client.post("/", data={"edit": "2"})  # ucinky parent
    client.post("/", data={"answer": "[12]"})
    packet = sessions[key]["contact"].snapshot()
    assert len(packet["question_answers"]) == 3
    assert packet["dialogue"]["patient_message_status"] == "submitted"
    assert packet["messages"][-2]["text"] == "Jsem zmatený."
    assert "Vaše zpráva: Jsem zmatený." in client.get("/").get_data(as_text=True)
