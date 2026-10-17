"""Message-selected relevant questions, synthetic extraction, no network."""

import json
import re
from base64 import b64encode
from copy import deepcopy
from types import SimpleNamespace

import pytest

from llm_intake.client import APIError
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
        seed_value=None,
        answer_calls=[],
        message_calls=[],
        directory=tmp_path,
    )

    class SyntheticClient:
        def extract_events(self, question, sources, questions, events):
            scenario.answer_calls.append((question.id, deepcopy(events)))
            if len(sources) == 1 and questions[-1] != question.text:
                if scenario.seed_value is None:
                    return {
                        "status": "unclear",
                        "value": None,
                        "source_index": None,
                        "evidence": None,
                        "follow_up": f"Upřesníte odpověď pro {question.id}?",
                    }
                return {
                    "status": "answered",
                    "value": scenario.seed_value,
                    "source_index": 0,
                    "evidence": sources[0],
                    "follow_up": None,
                }
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
    original_post = client.post

    def post_with_token(path, *args, **kwargs):
        body = kwargs.get("data", {})
        if path == "/patient" and "answer" in body and "submission_token" not in body:
            html = client.get("/patient").get_data(as_text=True)
            token = re.search(r'name="submission_token" value="([^"]+)"', html)
            if token:
                kwargs["data"] = {**body, "submission_token": token[1]}
        return original_post(path, *args, **kwargs)

    client.post = post_with_token
    client.environ_base["HTTP_AUTHORIZATION"] = "Basic " + b64encode(
        b"demo:synthetic-password"
    ).decode("ascii")
    client.post("/patient", data={"patient_id": "synthetic"})
    with client.session_transaction() as flask_session:
        scenario.key = flask_session["id"]
    scenario.client = client
    yield scenario
    sessions.pop(scenario.key, None)


def opening(scenario, text="Jsem unavený."):
    response = scenario.client.post(
        "/patient", data={"answer": text}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Odeslání se nezdařilo" not in response.get_data(as_text=True)
    return response


def answer_targets(scenario, values=None):
    values = values or {}
    visited = []
    while sessions[scenario.key]["contact"].state == "needs_answer":
        assert len(visited) < 12
        q = sessions[scenario.key]["contact"].active.question
        visited.append((q.questionnaire_id, q.id))
        value = values.get(q.id, 1 if q.kind == "skala_1_10" else 0)
        result = scenario.client.post(
            "/patient", data={"answer": json.dumps(value)}, follow_redirects=True
        )
        assert "Odeslání se nezdařilo" not in result.get_data(as_text=True)
    return visited


@pytest.mark.parametrize("form", list(TOPICS))
def test_master_selects_only_relevant_question_not_the_whole_form(browser, form):
    browser.topics = [TOPICS[form]]
    opening(browser)
    packet = sessions[browser.key]["contact"].snapshot()
    flow = packet["dialogue"]["flows"][0]
    question_id = TOPICS[form].split("/")[1]
    assert flow["mode"] == "targeted"
    assert flow["targets"] == [question_id]
    assert [q["question_id"] for q in flow["questions"]] == [question_id]
    assert answer_targets(browser) == [(form, question_id)]
    browser.client.post("/patient", data={"confirm": "1"})
    stored = json.loads((browser.directory / "pacienti/synthetic.json").read_text())
    checkin = stored["checkiny"][-1]
    assert [a["otazka_id"] for a in checkin["dotazniky"][0]["odpovedi"]] == [
        question_id
    ]
    assert checkin["zprava_pacienta"] == "Jsem unavený."


def test_complete_master_answer_is_reused_without_repeating_the_question(browser):
    browser.seed_value = 0
    opening(browser, "Odpočinek mi pomůže.")
    assert sessions[browser.key]["contact"].state == "complete"
    assert (
        len(browser.answer_calls) == 1
    )  # Existing message interpreted for the target.
    response = browser.client.get("/patient").get_data(as_text=True)
    assert "Zkontrolujte všechny odpovědi" in response
    assert "<textarea" not in response
    answer = sessions[browser.key]["contact"].snapshot()["question_answers"][0]
    assert answer["turns"][0]["question"] == "Jak se dnes cítíte?"
    assert answer["turns"][0]["answer"] == "Odpočinek mi pomůže."


def test_several_topics_do_not_expand_into_complete_questionnaires(browser):
    browser.topics = list(TOPICS.values())
    opening(browser)
    visited = answer_targets(browser)
    assert len(visited) == 4
    assert set(visited) == {tuple(topic.split("/")) for topic in TOPICS.values()}
    assert sessions[browser.key]["contact"].snapshot()["dialogue"]["max_questions"] == 6


def test_only_relevant_conditional_branch_is_added(browser):
    browser.topics = ["nezadouci_ucinky/krvaceni"]
    opening(browser)
    visited = answer_targets(
        browser, {"krvaceni": 1, "krvaceni_popis": "Syntetický popis."}
    )
    assert [q for _, q in visited] == ["krvaceni", "krvaceni_popis"]
    assert "pocit" not in [q for _, q in visited]


def test_new_topic_adds_only_its_question(browser):
    opening(browser)
    browser.next_topics = [TOPICS["psychoonkologicky_screening"]]
    assert answer_targets(browser) == [
        ("nezadouci_ucinky", "unava"),
        ("psychoonkologicky_screening", "uzkost"),
    ]


@pytest.mark.parametrize("kind", ["no_facts", "absent", "caregiver", "unknown"])
def test_no_relevant_patient_topic_does_not_invent_questions(browser, kind):
    if kind == "no_facts":
        browser.topics = []
    elif kind == "absent":
        browser.presence = "absent"
    else:
        browser.subject = kind
    opening(browser, "Syntetická zpráva.")
    assert not sessions[browser.key]["contact"].snapshot()["dialogue"]["flows"]
    assert not browser.answer_calls


def test_targeted_flow_keeps_initial_fever_and_measurement_export(browser, monkeypatch):
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
    assert answer_targets(browser) == [("nezadouci_ucinky", "teplota")]
    browser.client.post("/patient", data={"confirm": "1"})
    result = sessions[browser.key]["assessment"]
    assert (
        result["triage_inputs"]["prepared"]["vital_signs"]["teplota_c"]["hodnota"]
        == 38.5
    )
    assert any(r["rule_id"] == "fever" for r in result["reasons"])
    stored = json.loads((browser.directory / "pacienti/synthetic.json").read_text())
    assert stored["checkiny"][-1]["vitalni_funkce"]["teplota_c"]["hodnota"] == 38.5
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["synthetic"])
    assert browser.client.get("/team").status_code == 200


def test_duplicate_master_submission_is_not_an_answer_to_the_target(browser):
    from web.event_store import EventStore

    html = browser.client.get("/patient").get_data(as_text=True)
    token = re.search(r'name="submission_token" value="([^\"]+)"', html)[1]
    body = {"answer": "  Jsem unavený.\n", "submission_token": token}
    assert browser.client.post("/patient", data=body).status_code == 302
    calls = (len(browser.message_calls), len(browser.answer_calls))
    root = sessions[browser.key]["contact"].snapshot()["message"]
    assert (
        EventStore(browser.directory / "events.sqlite3")
        .get(browser.key, root["id"])
        .message.text
        == body["answer"]
    )
    assert browser.client.post("/patient", data=body).status_code == 302
    assert calls == (len(browser.message_calls), len(browser.answer_calls))
    assert sessions[browser.key]["contact"].active.question.id == "unava"


def test_opening_failure_retains_receipt_and_allows_retry(browser):
    browser.fail = True
    result = browser.client.post("/patient", data={"answer": "Jsem unavený."})
    assert "synthetic model failure" in result.get_data(as_text=True)
    assert sessions[browser.key]["contact"] is None
    browser.fail = False
    opening(browser)
    assert sessions[browser.key]["contact"].active.question.id == "unava"
