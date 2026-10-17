"""Receipt before LLM, duplicate POSTs, failures and corrections; synthetic only."""

import re
import sqlite3
from copy import deepcopy

import pytest

from llm_intake.client import APIError, Client
from tests.test_survey_recovery import (
    post_answer,
    start_review,
    survey,
)
from web.app import app, sessions, submission_serializer
from web.event_store import EventStore

# Re-export the shared fixture so pytest discovers it in this module.
__all__ = ["survey"]


def form(client, text):
    html = client.get("/patient").get_data(as_text=True)
    token = re.search(r'name="submission_token" value="([^"]+)"', html)[1]
    return {"answer": text, "submission_token": token}


def ticket(body):
    with app.app_context():
        return submission_serializer().loads(body["submission_token"])


def test_original_is_committed_before_even_creating_the_llm_client(survey, monkeypatch):
    client, key, directory, _ = survey
    body = form(client, "  Odpočinek pomůže.\n")
    source = ticket(body)
    store = EventStore(directory / "events.sqlite3")
    original_factory = Client.from_env

    def create_client():
        saved = store.get(key, source["id"])
        assert saved.message.text == body["answer"]
        assert saved.message.question == "Jak se dnes cítíte?"
        assert saved.message.author == "patient"
        return original_factory()

    monkeypatch.setattr(Client, "from_env", create_client)
    assert client.post("/patient", data=body).status_code == 302
    packet = sessions[key]["contact"].snapshot()
    assert packet["message"]["id"] == source["id"]
    assert packet["message"]["text"] == body["answer"]
    assert (
        store.get(key, source["id"]).message.available_at
        == packet["message"]["available_at"]
    )


def test_failed_first_extraction_retains_original_and_explicit_receipt(
    survey, monkeypatch
):
    client, key, directory, _ = survey
    body = form(client, "Původní zpráva.\n")
    source = ticket(body)

    def fail(_):
        raise APIError("synthetic timeout")

    monkeypatch.setattr("web.app.MasterExtractor", lambda _, **kwargs: fail)
    response = client.post("/patient", data=body)
    html = response.get_data(as_text=True)
    assert "Zpráva je uložená, zpracování se nezdařilo" in html
    assert "readonly" in html
    assert sessions[key]["contact"] is None
    store = EventStore(directory / "events.sqlite3")
    original = store.get(key, source["id"])
    assert original.message.text == body["answer"]
    assert not list(directory.rglob("*.json"))
    assert "readonly" in client.get("/patient").get_data(as_text=True)
    assert client.post("/patient", data=body).status_code == 200
    assert store.contact_messages(key, source["contact_id"]) == [original]


def test_failed_targeted_extraction_can_retry_the_same_source(survey, monkeypatch):
    client, key, directory, _ = survey
    post_answer(client, "Nevím.")
    body = form(client, "Ano.")
    source = ticket(body)
    before = sessions[key]["contact"].snapshot()

    def fail(*_):
        raise APIError("synthetic targeted timeout")

    with monkeypatch.context() as patch:
        patch.setattr(sessions[key]["contact"].active, "_extract_with_events", fail)
        response = client.post("/patient", data=body)
    assert "zpracování se nezdařilo" in response.get_data(as_text=True)
    assert sessions[key]["contact"].snapshot() == before
    store = EventStore(directory / "events.sqlite3")
    original = store.get(key, source["id"])
    assert original.question_id == "nezadouci_ucinky/unava"
    assert original.message.question == "Pomůže vám odpočinek?"
    assert client.post("/patient", data=body).status_code == 302
    assert len(store.contact_messages(key, source["contact_id"])) == 2
    assert store.get(key, source["id"]) == original
    assert sessions[key]["contact"].snapshot()["messages"][-1]["id"] == source["id"]


def test_stale_post_cannot_answer_the_next_question_or_repeat_llm(survey):
    client, key, directory, calls = survey
    body = form(client, "Nevím.")
    source = ticket(body)
    assert client.post("/patient", data=body).status_code == 302
    before = sessions[key]["contact"].snapshot()
    count = len(calls)
    assert client.post("/patient", data=body).status_code == 302
    assert sessions[key]["contact"].snapshot() == before
    assert len(calls) == count
    assert (
        len(
            EventStore(directory / "events.sqlite3").contact_messages(
                key, source["contact_id"]
            )
        )
        == 1
    )


def test_duplicate_post_after_confirmation_does_not_create_a_new_checkin(survey):
    client, key, directory, calls = survey
    body = form(client, "Odpočinek pomůže.")
    client.post("/patient", data=body)
    client.post("/patient", data={"confirm": "1"})
    path = directory / "pacienti" / "ONC-002.json"
    original = path.read_bytes()
    count = len(calls)
    assert client.post("/patient", data=body).status_code == 302
    assert sessions[key]["done"]
    assert path.read_bytes() == original
    assert len(calls) == count


def test_lost_memory_keeps_receipt_and_rejects_reprocessing_old_post(survey):
    client, key, directory, calls = survey
    body = form(client, "Nevím.")
    source = ticket(body)
    client.post("/patient", data=body)
    count = len(calls)
    sessions.pop(key)
    response = client.post("/patient", data=body)
    assert "Zpráva je uložená, ale přerušený rozhovor" in response.get_data(
        as_text=True
    )
    assert len(calls) == count
    assert sessions[key]["contact"] is None
    assert not sessions[key]["done"]
    assert (
        len(
            EventStore(directory / "events.sqlite3").contact_messages(
                key, source["contact_id"]
            )
        )
        == 1
    )


def test_receipt_failure_prevents_llm_and_keeps_text_editable(survey, monkeypatch):
    client, key, directory, _ = survey
    body = form(client, "Neztratit tento text.")
    source = ticket(body)

    def fail(*_, **__):
        raise sqlite3.OperationalError("synthetic full disk")

    def unexpected_client():
        pytest.fail("LLM client must not be created before durable receipt")

    with monkeypatch.context() as patch:
        patch.setattr(EventStore, "accept", fail)
        patch.setattr(Client, "from_env", unexpected_client)
        html = client.post("/patient", data=body).get_data(as_text=True)
    assert "Odpovědi se nepodařilo uložit" in html
    assert body["answer"] in html
    assert "readonly" not in html
    assert "Zpráva je uložená" not in html
    assert sessions[key]["contact"] is None
    assert EventStore(directory / "events.sqlite3").get(key, source["id"]) is None
    assert client.post("/patient", data=body).status_code == 302


@pytest.mark.parametrize("invalid", ["missing", "changed", "other_browser"])
def test_invalid_submission_is_rejected_before_llm(survey, monkeypatch, invalid):
    client, key, directory, _ = survey
    body = form(client, "Syntetická zpráva.")
    if invalid == "missing":
        body.pop("submission_token")
    elif invalid == "changed":
        body["submission_token"] += "invalid"
    else:
        client = app.test_client()
        client.post("/patient", data={"patient_id": "ONC-002"})

    def unexpected_client():
        pytest.fail("Invalid submissions must not call the model")

    monkeypatch.setattr(Client, "from_env", unexpected_client)
    response = client.post("/patient", data=body)
    assert response.status_code == 200
    assert "Odeslání se nezdařilo" in response.get_data(as_text=True)
    assert sessions[key]["contact"] is None
    assert not (directory / "events.sqlite3").exists()


def test_review_correction_retains_source_and_links_to_original(survey):
    client, key, directory, _ = survey
    start_review(client)
    packet = sessions[key]["contact"].snapshot()
    original_id = packet["message"]["id"]
    client.post("/patient", data={"edit": "0"})
    post_answer(client, "Oprava.")
    packet = sessions[key]["contact"].snapshot()
    correction_id = packet["messages"][-1]["id"]
    store = EventStore(directory / "events.sqlite3")
    correction = store.get(key, correction_id)
    assert correction.corrects_event_id == original_id
    assert correction.question_id == "nezadouci_ucinky/unava"
    assert correction.message.source == "targeted_answer"
    assert store.get(key, original_id).message.text == "Odpočinek pomůže."
    assert len(store.contact_messages(key, correction.contact_id)) == 2


def test_failed_source_can_be_corrected_with_a_new_id(survey, monkeypatch):
    client, key, directory, _ = survey
    body = form(client, "Původní zpráva.")
    source = ticket(body)

    def fail(_):
        raise APIError("synthetic timeout")

    with monkeypatch.context() as patch:
        patch.setattr("web.app.MasterExtractor", lambda _, **kwargs: fail)
        client.post("/patient", data=body)
    response = client.post(
        "/patient",
        data={"replace_message": "1", "submission_token": body["submission_token"]},
    )
    assert response.status_code == 302
    corrected_body = form(client, "Odpočinek pomůže.")
    assert ticket(corrected_body)["id"] != source["id"]
    assert client.post("/patient", data=corrected_body).status_code == 302
    records = EventStore(directory / "events.sqlite3").contact_messages(
        key, source["contact_id"]
    )
    assert len(records) == 2
    assert records[0].message.text == body["answer"]
    assert records[1].corrects_event_id == source["id"]


def test_same_token_with_changed_text_is_not_a_new_answer(survey):
    client, key, directory, calls = survey
    body = form(client, "Nevím.")
    source = ticket(body)
    client.post("/patient", data=body)
    before = deepcopy(sessions[key]["contact"].snapshot())
    count = len(calls)
    response = client.post("/patient", data={**body, "answer": "Jiný text."})
    assert "již obsahuje jinou zprávu" in response.get_data(as_text=True)
    assert sessions[key]["contact"].snapshot() == before
    assert len(calls) == count
    assert (
        len(
            EventStore(directory / "events.sqlite3").contact_messages(
                key, source["contact_id"]
            )
        )
        == 1
    )
