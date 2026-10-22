"""Application smoke checks; LLM and SMTP calls are blocked."""

import json
import re
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from llm_intake.client import APIError, Client
from llm_intake.core import load_questions
from llm_intake.master import MasterExtractor
from llm_intake.master_contract import Fact, MessageEvent
from meddi.loader import list_patient_ids, load_patient
from web.app import app, sessions
from web.event_store import EventStore


@pytest.fixture
def web(monkeypatch, tmp_path):
    def no_external_calls(*args, **kwargs):
        pytest.fail("Smoke checks must not contact an external service")

    monkeypatch.setattr(Client, "send", no_external_calls)
    monkeypatch.setattr("notifications.mailer.send_notification", no_external_calls)
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "SECRET_KEY", "synthetic-test-secret")
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "test")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "synthetic-password")
    monkeypatch.setitem(app.config, "DATA_DIR", tmp_path)
    sessions.clear()
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Basic dGVzdDpzeW50aGV0aWMtcGFzc3dvcmQ="
    yield SimpleNamespace(client=client, path=tmp_path, monkeypatch=monkeypatch)
    sessions.clear()


def submit(client, text):
    page = client.get("/patient").get_data(as_text=True)
    token = re.search(r'name="submission_token" value="([^"]+)"', page)[1]
    return client.post(
        "/patient",
        data={"answer": text, "submission_token": token},
        follow_redirects=True,
    )


def test_authentication_protects_pages_and_assets(web):
    for path in ("/", "/patient", "/team", "/static/style.css"):
        for authorization in ("", "Basic aW52YWxpZDppbnZhbGlk"):
            response = web.client.get(path, headers={"Authorization": authorization})
            assert response.status_code == 401


def test_missing_credentials_disable_access(web):
    web.monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "")
    assert web.client.get("/").status_code == 503


def test_bundled_profiles_pages_and_assets_load(web):
    for path in ("/", "/patient", "/patient/demo", "/team"):
        assert web.client.get(path).status_code == 200
    profiles = list_patient_ids()
    assert profiles
    for patient_id in profiles:
        assert load_patient(patient_id)["patient_id"] == patient_id
        response = web.client.post(
            "/patient/demo", data={"patient_id": patient_id}, follow_redirects=True
        )
        assert response.status_code == 200
        response = web.client.get(f"/patients/{patient_id}/report")
        assert response.status_code == 200
        assets = re.findall(r'(?:src|href)="(/(?:static|assets)/[^"?]+)', response.text)
        assert assets
        for asset in set(assets):
            assert web.client.get(asset).status_code == 200
    assert web.client.get("/patients/unknown/report").status_code == 404


def test_intake_resources_build_provider_requests(web):
    provider = Client("synthetic-key", model="test-model")
    questions = load_questions()
    assert questions
    for question in questions:
        payload = provider.payload(question, ["Synthetic answer"])
        assert payload["response_format"]["json_schema"]["strict"]
    message = MessageEvent(
        "test-message",
        list_patient_ids()[0],
        "Synthetic check-in",
        datetime.now(UTC).isoformat(),
        "master_question",
        "patient",
        "Jak se dnes cítíte?",
    )
    payload = MasterExtractor(provider).payload(message)
    assert payload["messages"][-1]["content"]
    assert payload["response_format"]["json_schema"]["strict"]


def test_checkin_can_be_confirmed_saved_and_reopened(web):
    class Model:
        def extract_events(self, question, sources, questions, events):
            return {
                "status": "answered",
                "value": 0,
                "source_index": len(sources) - 1,
                "evidence": sources[-1],
                "follow_up": None,
            }

    def extract(message):
        return [
            Fact(
                "overall_feeling",
                "present",
                message.text,
                "patient",
                value=message.text,
            )
        ]

    web.monkeypatch.setattr(Client, "from_env", Model)
    web.monkeypatch.setattr("web.app.MasterExtractor", lambda *args, **kwargs: extract)
    patient_id = list_patient_ids()[0]
    web.client.post("/patient", data={"patient_id": patient_id})
    text = "Dnes se cítím dobře."
    assert submit(web.client, text).status_code == 200
    with web.client.session_transaction() as browser:
        key = browser["id"]
    for _ in range(app.config["MAX_QUESTIONS"]):
        contact = sessions[key]["contact"]
        if contact.state == "complete":
            break
        assert contact.state == "needs_answer"
        assert submit(web.client, contact.active.question.options[0]).status_code == 200
    assert sessions[key]["contact"].state == "complete"
    assert web.client.post("/patient", data={"confirm": "1"}).status_code == 302
    path = web.path / "pacienti" / f"{patient_id}.json"
    saved = json.loads(path.read_text())["checkiny"][-1]
    assert saved["zprava_pacienta"] == text
    assert saved["triage_assessment"]["color"] in {"green", "yellow", "orange", "red"}
    contact_id = sessions[key]["contact_id"]
    journal = EventStore(web.path / "events.sqlite3")
    assert journal.contact_messages(key, contact_id)[0].message.text == text
    sessions.clear()
    web.client.post("/patient/logout")
    web.client.post("/patient", data={"patient_id": patient_id})
    assert web.client.get("/patient").status_code == 200
    assert saved["checkin_id"] in web.client.get(f"/patients/{patient_id}/report").text
    assert web.client.get("/team").status_code == 200


def test_provider_failure_keeps_the_original_message(web):
    def unavailable():
        raise APIError("Provider unavailable")

    web.monkeypatch.setattr(Client, "from_env", unavailable)
    patient_id = list_patient_ids()[0]
    web.client.post("/patient", data={"patient_id": patient_id})
    response = submit(web.client, "Synthetic message retained during an outage")
    assert response.status_code == 200
    assert "Provider unavailable" in response.text
    with web.client.session_transaction() as browser:
        key = browser["id"]
    pending = sessions[key]["received_message"]
    stored = EventStore(web.path / "events.sqlite3").get(key, pending.id)
    assert stored.message.text == "Synthetic message retained during an outage"
    assert not (web.path / "pacienti" / f"{patient_id}.json").exists()
