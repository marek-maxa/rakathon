"""Message-selected complete questionnaires, synthetic extraction, no network."""

import json
from base64 import b64encode
from copy import deepcopy
from types import SimpleNamespace

import pytest

from llm_intake.client import APIError
from llm_intake.core import load_questions
from llm_intake.master_contract import Fact
from web.app import app, sessions

TOPICS = {
    "nezadouci_ucinky": "nezadouci_ucinky/unava",
    "psychoonkologicky_screening": "psychoonkologicky_screening/uzkost",
    "bolest_analgeticka_terapie": "bolest_analgeticka_terapie/nrs",
    "esas": "esas/unava",
}


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
    scenario = SimpleNamespace(
        topics=[TOPICS["nezadouci_ucinky"]],
        next_topics=[],
        presence="present",
        subject="patient",
        confusion=False,
        fail=False,
        opening_facts=None,
        answer_calls=[],
        message_calls=[],
        directory=tmp_path,
    )

    class SyntheticClient:
        def extract_events(self, question, sources, questions, events):
            scenario.answer_calls.append((question.id, deepcopy(events)))
            return {
                "status": "answered",
                "value": json.loads(sources[-1]),
                "source_index": len(sources) - 1,
                "evidence": sources[-1],
                "follow_up": None,
            }

    def extract_message(message):
        scenario.message_calls.append(message)
        if scenario.fail:
            raise APIError("synthetic model failure")
        facts = []
        if message.source == "master_question":
            if scenario.opening_facts is not None:
                return scenario.opening_facts
            if scenario.topics:
                facts.append(
                    Fact(
                        "fatigue",
                        scenario.presence,
                        message.text,
                        scenario.subject,
                        topic_ids=tuple(scenario.topics),
                    )
                )
            if scenario.confusion:
                facts.append(Fact("confusion", "present", message.text, "patient"))
        elif scenario.next_topics:
            facts.append(
                Fact(
                    "anxiety",
                    "present",
                    message.text,
                    "patient",
                    topic_ids=tuple(scenario.next_topics),
                )
            )
            scenario.next_topics = []
        return facts

    monkeypatch.setattr("web.app.Client.from_env", lambda: SyntheticClient())
    monkeypatch.setattr("web.app.MasterExtractor", lambda _: extract_message)
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Basic " + b64encode(
        b"demo:synthetic-password"
    ).decode("ascii")
    client.post("/", data={"patient_id": "synthetic"})
    with client.session_transaction() as flask_session:
        scenario.key = flask_session["id"]
    scenario.client = client
    yield scenario
    sessions.pop(scenario.key, None)


def opening(scenario, text="Jsem unavený."):
    response = scenario.client.post("/", data={"answer": text}, follow_redirects=True)
    assert response.status_code == 200
    assert "Odeslání se nezdařilo" not in response.get_data(as_text=True)
    return response


def answer_forms(scenario, *, all_branches=False):
    visited = []
    while sessions[scenario.key]["contact"].state == "needs_answer":
        assert len(visited) < 50
        question = sessions[scenario.key]["contact"].active.question
        visited.append((question.questionnaire_id, question.id))
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
        response = scenario.client.post(
            "/", data={"answer": json.dumps(value)}, follow_redirects=True
        )
        assert response.status_code == 200
        assert "Odeslání se nezdařilo" not in response.get_data(as_text=True)
    assert sessions[scenario.key]["contact"].state in {"complete", "unresolved"}
    assert "Zkontrolujte všechny odpovědi" in scenario.client.get("/").get_data(
        as_text=True
    )
    return visited


@pytest.mark.parametrize("form", list(TOPICS))
def test_opening_selects_entire_relevant_form_and_is_exported_as_message(browser, form):
    browser.topics = [TOPICS[form]]
    html = browser.client.get("/").get_data(as_text=True)
    assert "Jak se dnes cítíte?" in html
    assert 'name="questionnaire_id"' not in html
    opening(browser)
    assert len(browser.message_calls) == 1
    assert not browser.answer_calls  # No targeted API call before initial triage.
    contact = sessions[browser.key]["contact"]
    packet = contact.snapshot()
    assert packet["dialogue"]["selected_questionnaire_ids"] == [form]
    assert packet["dialogue"]["flows"][0]["mode"] == "questionnaire"
    assert sessions[browser.key]["assessment"]["intake"]["facts"] == packet["facts"]
    visited = answer_forms(browser, all_branches=True)
    assert visited == [
        (q.questionnaire_id, q.id)
        for q in load_questions()
        if q.questionnaire_id == form
    ]
    assert not list(browser.directory.rglob("*.json"))
    response = browser.client.post("/", data={"confirm": "1"}, follow_redirects=True)
    assert "Odpovědi jsou uložené." in response.get_data(as_text=True)
    checkin = json.loads(
        (browser.directory / "pacienti/synthetic.json").read_text(encoding="utf-8")
    )["checkiny"][-1]
    assert [row["dotaznik_id"] for row in checkin["dotazniky"]] == [form]
    assert checkin["zprava_pacienta"] == "Jsem unavený."
    assert (
        checkin["triage_assessment"]["intake"]["message"]["source"] == "master_question"
    )


def test_all_relevant_forms_are_selected_once_and_traversed_without_six_question_cutoff(
    browser,
):
    browser.topics = list(TOPICS.values()) + ["nezadouci_ucinky/prujem"]
    opening(browser, "Mám několik různých potíží.")
    packet = sessions[browser.key]["contact"].snapshot()
    assert packet["dialogue"]["selected_questionnaire_ids"] == list(TOPICS)
    visited = answer_forms(browser, all_branches=True)
    assert len(visited) == 49
    assert len(set(visited)) == 49
    assert visited == [(q.questionnaire_id, q.id) for q in load_questions()]
    assert all(
        flow["state"] == "complete"
        for flow in sessions[browser.key]["contact"].snapshot()["dialogue"]["flows"]
    )
    assert "Závěrečná zpráva" not in browser.client.get("/").get_data(as_text=True)


def test_opening_fact_affects_triage_immediately_and_survives_negative_answers(browser):
    browser.confusion = True
    opening(browser, "Jsem zmatený a unavený.")
    assert sessions[browser.key]["assessment"]["color"] == "red"
    assert len(browser.message_calls) == 1 and not browser.answer_calls
    visited = answer_forms(browser)
    assert [qid for _, qid in visited] == ["pocit", "sobestacnost", "ucinky"]
    browser.client.post("/", data={"confirm": "1"})
    checkin = json.loads(
        (browser.directory / "pacienti/synthetic.json").read_text(encoding="utf-8")
    )["checkiny"][-1]
    assert checkin["zprava_pacienta"] == "Jsem zmatený a unavený."
    assert checkin["triage_assessment"]["color"] == "red"
    assert sum(m.source == "master_question" for m in browser.message_calls) == 1


def test_initial_fever_measurement_survives_later_mild_questionnaire_choice(browser):
    browser.opening_facts = [
        Fact(
            "temperature",
            "present",
            "38.5",
            "patient",
            38.5,
            "degC",
            topic_ids=("nezadouci_ucinky/teplota",),
        )
    ]
    opening(browser, "Dnes mám 38.5 stupně.")
    answer_forms(browser, all_branches=True)
    browser.client.post("/", data={"confirm": "1"})
    result = sessions[browser.key]["assessment"]
    prepared = result["triage_inputs"]["prepared"]
    assert prepared["vital_signs"]["teplota_c"]["hodnota"] == 38.5
    assert any(r["rule_id"] == "fever" for r in result["reasons"])


@pytest.mark.parametrize("kind", ["no_facts", "absent", "caregiver", "unknown"])
def test_no_relevant_patient_topic_does_not_invent_a_form(browser, kind):
    if kind == "no_facts":
        browser.topics = []
    elif kind == "absent":
        browser.presence = "absent"
    else:
        browser.subject = kind
    opening(browser, "Syntetická zpráva.")
    packet = sessions[browser.key]["contact"].snapshot()
    assert packet["dialogue"]["selected_questionnaire_ids"] == []
    assert not browser.answer_calls
    html = browser.client.get("/").get_data(as_text=True)
    assert "nevybrali žádný navazující dotazník" in html
    assert "Vaše úvodní zpráva: Syntetická zpráva." in html
    browser.client.post("/", data={"confirm": "1"})
    assert sessions[browser.key]["packet"]["message"]["text"] == "Syntetická zpráva."


def test_unmapped_urgent_fact_is_evaluated_even_when_no_form_is_selected(browser):
    browser.topics = []
    browser.confusion = True
    opening(browser, "Jsem zmatený.")
    assert not browser.answer_calls
    assert sessions[browser.key]["assessment"]["color"] == "red"
    assert not sessions[browser.key]["contact"].snapshot()["dialogue"]["flows"]
    browser.client.post("/", data={"confirm": "1"})
    assert sessions[browser.key]["done"]
    assert sessions[browser.key]["assessment"]["color"] == "red"


def test_opening_failure_retains_text_and_can_be_retried(browser):
    browser.fail = True
    response = browser.client.post("/", data={"answer": "Jsem unavený."})
    html = response.get_data(as_text=True)
    assert "synthetic model failure" in html
    assert ">Jsem unavený.</textarea>" in html
    assert sessions[browser.key]["contact"] is None
    assert not browser.answer_calls and not list(browser.directory.rglob("*.json"))
    browser.fail = False
    opening(browser)
    assert sessions[browser.key]["contact"].state == "needs_answer"


def test_confirmation_and_old_selection_actions_cannot_bypass_initial_message(browser):
    for action in (
        {"confirm": "1"},
        {"questionnaire_id": "nezadouci_ucinky"},
        {"skip_message": "1"},
        {"answer": "  "},
    ):
        response = browser.client.post("/", data=action)
        assert "Odeslání se nezdařilo" in response.get_data(as_text=True)
    assert not browser.message_calls and sessions[browser.key]["contact"] is None
    opening(browser)
    before = sessions[browser.key]["contact"].snapshot()
    browser.client.post("/", data={"confirm": "1"})
    assert sessions[browser.key]["contact"].snapshot() == before


def test_edit_parent_removes_descendants_but_keeps_initial_message(browser):
    opening(browser)
    answer_forms(browser, all_branches=True)
    browser.client.post("/", data={"edit": "2"})
    browser.client.post("/", data={"answer": "[12]"})
    packet = sessions[browser.key]["contact"].snapshot()
    assert len(packet["question_answers"]) == 3
    assert packet["message"]["text"] == "Jsem unavený."
    assert "Vaše úvodní zpráva: Jsem unavený." in browser.client.get("/").get_data(
        as_text=True
    )


def test_new_topic_in_followup_can_add_another_complete_form(browser):
    opening(browser)
    browser.next_topics = [TOPICS["psychoonkologicky_screening"]]
    visited = answer_forms(browser)
    assert {form for form, _ in visited} == {
        "nezadouci_ucinky",
        "psychoonkologicky_screening",
    }
    assert [qid for form, qid in visited if form == "psychoonkologicky_screening"] == [
        q.id
        for q in load_questions()
        if q.questionnaire_id == "psychoonkologicky_screening"
    ]
