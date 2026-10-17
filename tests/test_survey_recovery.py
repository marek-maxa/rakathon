"""Recovered survey flow: synthetic inputs, no external model calls."""

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from llm_intake.client import APIError, Client
from llm_intake.dialogue import MasterDialogue
from llm_intake.master_contract import Fact, MessageEvent
from web.app import app, sessions
from web.patient_store import append_checkins, load_patient


def answered(value, sources):
    return {
        "status": "answered",
        "value": value,
        "source_index": len(sources) - 1,
        "evidence": sources[-1],
        "follow_up": None,
    }


def unclear():
    return {
        "status": "unclear",
        "value": None,
        "source_index": None,
        "evidence": None,
        "follow_up": "Pomůže vám odpočinek?",
    }


def event(
    text="Odpočinek pomůže.", id="synthetic-opening", question="Jak se dnes cítíte?"
):
    return MessageEvent(
        id,
        "ONC-002",
        text,
        "2026-10-17T10:00:00+02:00",
        "master_question" if id == "synthetic-opening" else "targeted_answer",
        "patient",
        question,
    )


def fatigue(message):
    return [Fact("fatigue", "present", message.text, "patient")]


@pytest.fixture
def survey(monkeypatch, tmp_path):
    patients = {
        "ONC-001": {
            "patient_id": "ONC-001",
            "demografie": {"jmeno_fiktivni": "Synthetic One"},
        },
        "ONC-002": {
            "patient_id": "ONC-002",
            "demografie": {"jmeno_fiktivni": "Synthetic Two"},
        },
    }
    source_directory = tmp_path / "source"
    source_directory.mkdir()
    for patient_id, patient in patients.items():
        patient["lecba"] = {"rezim": "synthetic context"}
        patient["checkiny"] = [
            {
                "patient_id": patient_id,
                "checkin_id": f"{patient_id}-HISTORY",
                "datum": "2026-10-01",
                "cas": "10:00",
                "cyklus": None,
                "dotazniky": [],
                "vitalni_funkce": {},
            }
        ]
        (source_directory / f"{patient_id}.json").write_text(
            json.dumps(patient, ensure_ascii=False), encoding="utf-8"
        )

    def load_source(patient_id):
        return json.loads(
            (source_directory / f"{patient_id}.json").read_text(encoding="utf-8")
        )

    monkeypatch.setattr("web.patient_store.load_source_patient", load_source)
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: list(patients))
    monkeypatch.setattr("web.app.list_patient_ids", lambda: list(patients))
    monkeypatch.setattr("web.app.load_patient", patients.__getitem__)
    directory = tmp_path / "data"
    monkeypatch.setitem(app.config, "DATA_DIR", directory)
    monkeypatch.setitem(app.config, "TESTING", True)
    calls = []

    class SyntheticClient:
        def extract_events(self, question, sources, questions, events):
            calls.append(deepcopy(events))
            if sources[-1] == "Nevím.":
                return unclear()
            return answered(1 if sources[-1] == "Oprava." else 0, sources)

    monkeypatch.setattr(Client, "from_env", lambda: SyntheticClient())
    monkeypatch.setattr("web.app.MasterExtractor", lambda _: fatigue)
    client = app.test_client()
    assert client.post("/patient", data={"patient_id": "ONC-002"}).status_code == 302
    with client.session_transaction() as flask_session:
        key = flask_session["id"]
    yield client, key, directory, calls
    sessions.pop(key, None)


def start_review(client):
    response = post_answer(client, "Odpočinek pomůže.", follow_redirects=True)
    assert response.status_code == 200
    assert "Zkontrolujte všechny odpovědi" in response.get_data(as_text=True)


def post_answer(client, text, **kwargs):
    html = client.get("/patient").get_data(as_text=True)
    token = re.search(r'name="submission_token" value="([^"]+)"', html)[1]
    return client.post(
        "/patient", data={"answer": text, "submission_token": token}, **kwargs
    )


def test_review_then_save_uses_selected_patient_and_survives_memory_loss(survey):
    client, key, directory, calls = survey
    source = directory.parent / "source" / "ONC-002.json"
    original = source.read_bytes()
    start_review(client)
    assert not list(directory.rglob("*.json"))
    assert not sessions[key]["contact"].snapshot()["question_answers"][0]["confirmed"]
    response = client.post(
        "/patient",
        data={"confirm": "1", "patient_id": "ONC-001"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert "Odpovědi jsou uložené." in html
    assert "/patients/ONC-002/report" not in html
    paths = list(directory.rglob("*.json"))
    assert len(paths) == 1 and paths[0] == directory / "pacienti" / "ONC-002.json"
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["patient_id"] == "ONC-002"
    assert source.read_bytes() == original
    assert record["lecba"] == json.loads(original)["lecba"]
    assert record["checkiny"][:-1] == json.loads(original)["checkiny"]
    checkin = record["checkiny"][-1]
    assert checkin["patient_id"] == "ONC-002"
    assert checkin["dotazniky"][0]["odpovedi"][0]["odpoved_index"] == 0
    assert all(e["patient_id"] == "ONC-002" for turn in calls for e in turn)
    sessions.pop(key)
    assert json.loads(paths[0].read_text(encoding="utf-8")) == record


def test_review_edit_and_follow_up_keep_profile_and_sources(survey):
    client, key, directory, _ = survey
    response = post_answer(client, "Nevím.", follow_redirects=True)
    assert "Pomůže vám odpočinek?" in response.get_data(as_text=True)
    before = sessions[key]["contact"].snapshot()
    assert client.get("/").status_code == 200
    assert client.get("/team").status_code == 200
    assert "Pomůže vám odpočinek?" in client.get("/patient").get_data(as_text=True)
    assert sessions[key]["contact"].snapshot() == before
    post_answer(client, "Ano.")
    client.post("/patient", data={"edit": "0"})
    assert sessions[key]["contact"].state == "needs_correction"
    response = post_answer(client, "Oprava.", follow_redirects=True)
    assert "Zkontrolujte všechny odpovědi" in response.get_data(as_text=True)
    client.post("/patient", data={"confirm": "1"})
    record = json.loads(next(directory.rglob("*.json")).read_text(encoding="utf-8"))
    checkin = record["checkiny"][-1]
    assert checkin["dotazniky"][0]["odpovedi"][0]["odpoved_index"] == 1
    assert checkin["zprava_pacienta"] == "Nevím.\nAno.\nOprava."


def test_follow_up_and_review_precede_triage_result(survey):
    client, key, directory, calls = survey
    response = post_answer(client, "Nevím.", follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Pomůže vám odpočinek?" in html
    assert 'name="answer"' in html
    assert "Výsledek triáže:" not in html
    assert "Triáž podle dostupných údajů" not in html
    assert "Zkontrolujte všechny odpovědi" not in html
    assert sessions[key]["assessment"]  # Evaluation still runs during collection.
    assert not list(directory.rglob("*.json"))

    response = post_answer(client, "Ano.", follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Zkontrolujte všechny odpovědi" in html
    assert "Výsledek triáže:" not in html
    assert not list(directory.rglob("*.json"))
    assert calls[-1][-1]["question"] == "Pomůže vám odpočinek?"

    response = client.post("/patient", data={"confirm": "1"}, follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Odpovědi jsou uložené." in html
    assert "Výsledek triáže:" in html
    assert len(list(directory.rglob("*.json"))) == 1


@pytest.mark.parametrize("color", [None, "green", "yellow", "orange", "red"])
def test_assessment_waits_for_confirmation(survey, monkeypatch, color):
    client, _, _, _ = survey
    assessment = {"color": color, "requires_review": True, "reasons": []}
    monkeypatch.setattr("web.app.assess_contact", lambda *_: assessment)
    start_review(client)
    assert "Výsledek triáže:" not in client.get("/patient").get_data(as_text=True)
    response = client.post("/patient", data={"confirm": "1"}, follow_redirects=True)
    assert "Výsledek triáže:" in response.get_data(as_text=True)


def test_red_finding_does_not_hide_or_finish_follow_up(survey, monkeypatch):
    client, key, directory, _ = survey

    def confusion_and_fatigue(message):
        return [
            Fact("confusion", "present", message.text, "patient"),
            *fatigue(message),
        ]

    monkeypatch.setattr("web.app.MasterExtractor", lambda _: confusion_and_fatigue)
    response = post_answer(client, "Nevím.", follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Průběžné upozornění" not in html
    assert 'triage-red">Červená' not in html
    assert sessions[key]["assessment"]["color"] == "red"
    assert "Výsledek triáže:" not in html
    assert "Pomůže vám odpočinek?" in html
    assert 'name="answer"' in html
    assert sessions[key]["contact"].state == "needs_answer"
    assert not sessions[key]["done"]
    assert not list(directory.rglob("*.json"))


@pytest.mark.parametrize(
    "action", [{"confirm": "1"}, {"answer": "Znovu."}, {"edit": "0"}, {"continue": "1"}]
)
def test_completed_submission_rejects_further_posts_without_rewriting(survey, action):
    client, key, directory, calls = survey
    start_review(client)
    client.post("/patient", data={"confirm": "1"})
    path = next(directory.rglob("*.json"))
    original = path.read_bytes()
    packet = sessions[key]["packet"]
    call_count = len(calls)
    response = client.post("/patient", data=action)
    assert response.status_code == 200
    assert "Odpovědi už jsou potvrzené." in response.get_data(as_text=True)
    assert path.read_bytes() == original
    assert len(list(directory.rglob("*.json"))) == 1
    assert sessions[key]["packet"] == packet
    assert len(calls) == call_count


def test_failed_atomic_save_keeps_review_retryable(survey, monkeypatch):
    client, key, directory, _ = survey
    start_review(client)
    before = sessions[key]["contact"].snapshot()
    with monkeypatch.context() as patch:

        def fail_replace(*_):
            raise OSError("synthetic disk error")

        patch.setattr(Path, "replace", fail_replace)
        response = client.post("/patient", data={"confirm": "1"})
    assert "Odpovědi se nepodařilo uložit." in response.get_data(as_text=True)
    assert not sessions[key]["done"]
    assert sessions[key]["contact"].snapshot() == before
    assert not list(directory.rglob("*.json"))
    assert not list((directory / "pacienti").iterdir())
    assert client.post("/patient", data={"confirm": "1"}).status_code == 302
    assert sessions[key]["done"]


def test_failed_extraction_preserves_current_state(survey, monkeypatch):
    client, key, _, _ = survey
    post_answer(client, "Nevím.")
    before = sessions[key]["contact"].snapshot()

    def fail_extract(*_):
        raise APIError("synthetic timeout")

    monkeypatch.setattr(
        sessions[key]["contact"].active, "_extract_with_events", fail_extract
    )
    response = post_answer(client, "Ano.")
    assert "synthetic timeout" in response.get_data(as_text=True)
    assert sessions[key]["contact"].snapshot() == before


def test_failed_append_preserves_existing_working_copy(survey, monkeypatch):
    client, key, directory, _ = survey
    start_review(client)
    client.post("/patient", data={"confirm": "1"})
    path = directory / "pacienti" / "ONC-002.json"
    original = path.read_bytes()
    client.post("/patient", data={"restart": "1"})
    start_review(client)
    with monkeypatch.context() as patch:

        def fail_replace(*_):
            raise OSError("synthetic disk error")

        patch.setattr(Path, "replace", fail_replace)
        assert client.post("/patient", data={"confirm": "1"}).status_code == 200
    assert path.read_bytes() == original
    assert not sessions[key]["done"]
    client.post("/patient", data={"confirm": "1"})
    assert len(json.loads(path.read_bytes())["checkiny"]) == 3


def test_report_includes_new_saved_answers_and_falls_back_to_source(survey):
    client, _, _, _ = survey
    assert client.get("/patients/ONC-002/report").status_code == 200
    start_review(client)
    client.post("/patient", data={"confirm": "1"})
    response = client.get("/patients/ONC-002/report")
    assert response.status_code == 200
    assert "WEB-" in response.get_data(as_text=True)
    assert "unava" in response.get_data(as_text=True)


def test_append_is_idempotent_and_validates_patient(survey):
    _, _, directory, _ = survey
    checkin = {"checkin_id": "SYNTHETIC-RETRY", "patient_id": "ONC-002"}
    with app.app_context():
        path = append_checkins("ONC-002", [checkin])
        append_checkins("ONC-002", [checkin])
        assert load_patient("ONC-002")["checkiny"][-1] == checkin
        assert len(load_patient("ONC-002")["checkiny"]) == 2
        original = path.read_bytes()
        with pytest.raises(ValueError):
            append_checkins("ONC-002", [{**checkin, "patient_id": "ONC-001"}])
        assert path.read_bytes() == original
    assert not (directory / "ONC-002").exists()


def test_concurrent_appends_do_not_lose_checkins(survey):
    from concurrent.futures import ThreadPoolExecutor

    def save(index):
        with app.app_context():
            append_checkins(
                "ONC-002",
                [
                    {
                        "patient_id": "ONC-002",
                        "checkin_id": f"SYNTHETIC-{index}",
                    }
                ],
            )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(save, range(8)))
    with app.app_context():
        checkins = load_patient("ONC-002")["checkiny"]
    assert len(checkins) == 9
    assert {c["checkin_id"] for c in checkins} == {
        "ONC-002-HISTORY",
        *(f"SYNTHETIC-{index}" for index in range(8)),
    }


def test_early_confirmation_and_invalid_edits_do_not_change_review(survey):
    client, key, directory, _ = survey
    assert client.post("/patient", data={"confirm": "1"}).status_code == 200
    post_answer(client, "Nevím.")
    assert "Nejprve dokončete všechny otázky." in client.post(
        "/patient", data={"confirm": "1"}
    ).get_data(as_text=True)
    post_answer(client, "Ano.")
    before = sessions[key]["contact"].snapshot()
    for index in ("-1", "99", "invalid"):
        assert client.post("/patient", data={"edit": index}).status_code == 200
        assert sessions[key]["contact"].snapshot() == before
    assert not list(directory.rglob("*.json"))


def test_restart_preserves_profile_and_creates_a_new_submission(survey):
    client, key, directory, _ = survey
    start_review(client)
    client.post("/patient", data={"confirm": "1"})
    response = client.post("/patient", data={"restart": "1"}, follow_redirects=True)
    assert "Úvodní otázka" in response.get_data(as_text=True)
    assert sessions[key]["patient_id"] == "ONC-002"
    start_review(client)
    client.post("/patient", data={"confirm": "1"})
    path = directory / "pacienti" / "ONC-002.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    assert len(record["checkiny"]) == 3
    assert len({c["checkin_id"] for c in record["checkiny"]}) == 3
    assert len(list(directory.rglob("*.json"))) == 1


def test_two_browser_sessions_save_under_their_own_patient_profiles(survey):
    client, _, directory, _ = survey
    other = app.test_client()
    other.post("/patient", data={"patient_id": "ONC-001"})
    with other.session_transaction() as flask_session:
        other_key = flask_session["id"]
    try:
        for browser in (client, other):
            start_review(browser)
            assert browser.post("/patient", data={"confirm": "1"}).status_code == 302
        for patient_id in ("ONC-001", "ONC-002"):
            path = directory / "pacienti" / f"{patient_id}.json"
            assert (
                json.loads(path.read_text(encoding="utf-8"))["patient_id"] == patient_id
            )
    finally:
        sessions.pop(other_key, None)


def test_limited_contact_saves_unresolved_answer_without_guessing(survey, monkeypatch):
    client, key, directory, _ = survey
    monkeypatch.setitem(app.config, "MAX_QUESTIONS", 1)
    response = post_answer(client, "Nevím.", follow_redirects=True)
    assert "Dosáhli jsme limitu dotazů." in response.get_data(as_text=True)
    client.post("/patient", data={"confirm": "1"})
    assert sessions[key]["done"]
    record = json.loads(next(directory.rglob("*.json")).read_text(encoding="utf-8"))
    answer = record["checkiny"][-1]["dotazniky"][0]["odpovedi"][0]
    assert answer["odpoved"] is None
    assert answer["barva"] is None


def test_draft_branch_and_revision_invalidate_conditional_descendants():
    def bleeding(message):
        return [Fact("bleeding", "present", message.text, "patient")]

    def extract(question, sources, *_):
        if question.id == "krvaceni_popis":
            if sources[-1] == "Krvácení.":
                return unclear()
            return answered(sources[-1], sources)
        return answered(0 if sources[-1] == "Oprava." else 1, sources)

    contact = MasterDialogue(bleeding, extract, bulk_confirmation=True)
    contact.start(event("Krvácení."))
    assert contact.active.question.id == "krvaceni_popis"
    contact.submit(event("Popis.", "reply-1", contact.active.next_question))
    assert len(contact.review_sessions) == 2
    assert all(
        not answer["confirmed"] for answer in contact.snapshot()["question_answers"]
    )
    contact.revise(0)
    contact.submit(event("Oprava.", "reply-2", contact.active.next_question))
    packet = contact.confirm_all()
    assert len(packet["question_answers"]) == 1
    assert packet["question_answers"][0]["value"] == 0
    assert packet["question_answers"][0]["confirmed"]


def test_bulk_confirmation_leaves_unresolved_answers_unconfirmed():
    contact = MasterDialogue(fatigue, lambda *_: unclear(), bulk_confirmation=True)
    contact.start(event("Nevím."))
    contact.submit(event("Nevím.", "reply-1", contact.active.next_question))
    packet = contact.confirm_all()
    assert packet["question_answers"][0]["state"] == "unresolved"
    assert packet["question_answers"][0]["value"] is None
    assert not packet["question_answers"][0]["confirmed"]
    with pytest.raises(ValueError):
        contact.confirm_all()


def test_triage_from_message_is_visible_after_confirmation_and_saved_for_report(
    survey, monkeypatch
):
    client, key, directory, _ = survey

    def confusion(message):
        return [Fact("confusion", "present", message.text, "patient")]

    monkeypatch.setattr("web.app.MasterExtractor", lambda _: confusion)
    response = post_answer(client, "Jsem zmatený.", follow_redirects=True)
    html = response.get_data(as_text=True)
    assert 'triage-red">Červená' not in html
    assert sessions[key]["assessment"]["reasons"]
    assert "Posouzení je neúplné" not in html
    assert not list(directory.rglob("*.json"))

    response = client.post("/patient", data={"confirm": "1"}, follow_redirects=True)
    assert "Odpovědi jsou uložené." in response.get_data(as_text=True)
    assert 'triage-red">Červená' in response.get_data(as_text=True)
    assert "Posouzení je neúplné" in response.get_data(as_text=True)
    path = directory / "pacienti" / "ONC-002.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    assessment = record["checkiny"][-1]["triage_assessment"]
    assert assessment["color"] == "red"
    assert assessment["kind"] == "meddi_contact_assessment"
    assert assessment["intake"] == sessions[key]["packet"]
    assert assessment["reasons"]

    sessions.pop(key)
    report = client.get("/patients/ONC-002/report")
    assert report.status_code == 200
    assert 'triage-red">Červená' in report.get_data(as_text=True)
    team = client.get("/team").get_data(as_text=True)
    assert record["checkiny"][-1]["checkin_id"] in team
    assert "/patients/ONC-002/report#triage-title" in team
    assert "Předání týmu: simulované" in team
