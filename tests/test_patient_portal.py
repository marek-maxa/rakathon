"""Patient portal: synthetic accounts, real saved triage, no external calls."""

import json
from copy import deepcopy
from datetime import timedelta

from llm_intake.client import APIError
from tests.test_mvp_scenarios import demo, finding, finish, post
from tests.test_web_triage import checkin
from web.app import app, sessions
from web.portal import build_portal, controls_for, update_controls
from web.triage import checkin_assessments

__all__ = ["demo"]


def baseline(demo):
    initial = checkin("BASELINE", "2026-10-16", feeling=2, temperature=37)
    initial["dotazniky"][0]["odpovedi"][0].update(
        odpoved="Necítím se dobře", barva="zluta"
    )
    demo.patient["checkiny"].append(initial)
    return initial


def html(demo):
    return demo.client.get("/patient").get_data(as_text=True)


def test_login_is_a_code_entry_and_empty_profile_is_not_green(demo):
    demo.client.post("/patient/logout")
    page = html(demo)
    assert "Váš přístupový kód" in page
    assert "Synthetic Person" not in page
    assert "<select" not in page
    assert "<textarea" not in page
    demo.client.post("/patient", data={"patient_id": "synthetic"})
    page = html(demo)
    assert "Zatím nemáme uložené hodnocení" in page
    assert "Jak se dnes cítíte?" in page
    assert "Moje údaje" in page
    assert "portal-status-green" not in page
    assert not demo.general_calls


def test_profile_switch_clears_author_pending_message_and_old_submission(
    demo, monkeypatch
):
    old = html(demo)
    import re

    from tests.test_web_events import ticket

    body = {
        "answer": "Stará odpověď",
        "submission_token": re.search(r'name="submission_token" value="([^"]+)"', old)[
            1
        ],
    }
    old_ticket = ticket(body)
    sessions[demo.key]["author"] = "caregiver"
    sessions[demo.key]["received_message"] = object()
    other = {
        "patient_id": "other",
        "demografie": {"jmeno_fiktivni": "Another Person"},
        "checkiny": [],
    }
    monkeypatch.setattr("web.app.list_patient_ids", lambda: ["synthetic", "other"])
    monkeypatch.setattr(
        "web.app.load_patient",
        lambda key: demo.patient if key == "synthetic" else other,
    )
    monkeypatch.setattr(
        "web.patient_store.load_source_patient",
        lambda key: deepcopy(demo.patient if key == "synthetic" else other),
    )
    response = demo.client.post(
        "/patient/demo", data={"patient_id": "other"}, follow_redirects=True
    )
    page = response.get_data(as_text=True)
    assert "Another Person" in page
    assert "Synthetic Person" not in page
    assert "Jak se dnes cítíte?" in page
    assert demo.key not in sessions
    with demo.client.session_transaction() as browser:
        assert browser["id"] != old_ticket["owner_id"]
        new_key = browser["id"]
    response = demo.client.post("/patient", data=body)
    assert "Odeslání nepatří tomuto rozhovoru" in response.get_data(as_text=True)
    assert not demo.general_calls
    sessions.pop(new_key, None)


def test_portal_matches_the_shared_assessment_and_does_not_mutate_on_get(demo):
    baseline(demo)
    before = deepcopy(demo.patient)
    view = build_portal(demo.patient, demo.at)
    assert view["assessment"] == checkin_assessments(demo.patient)[-1]
    assert {c["id"] for c in view["controls"]} == {
        "nezadouci_ucinky/pocit",
        "teplota_c",
    }
    html(demo)
    html(demo)
    assert demo.patient == before
    assert not demo.path.exists()
    assert not demo.general_calls


def test_targeted_control_updates_only_after_confirmation_and_survives_reload(demo):
    baseline(demo)
    response = demo.client.post(
        "/patient", data={"follow_up": "nezadouci_ucinky/pocit"}, follow_redirects=True
    )
    assert "Jak se celkově cítíte?" in response.get_data(as_text=True)
    assert not demo.general_calls
    post(demo, "Cítím se dobře, běžný stav.")
    assert not demo.path.exists()
    assert sessions[demo.key]["contact"].state == "complete"
    assert "Pro část sdělení prototyp nemá navazující otázky" not in html(demo)
    saved = finish(demo)
    record = json.loads(demo.path.read_text())
    control = next(
        c for c in record["portal_controls"] if c["id"] == "nezadouci_ucinky/pocit"
    )
    assert control["completed_checkin_id"] == saved["checkin_id"]
    assert saved["zdrojove_zpravy"][0]["question"] == "Jak se celkově cítíte?"
    assert saved["zdrojove_zpravy"][0]["source"] == "targeted_answer"
    assert saved["triage_assessment"]["color"] == "green"
    assert saved["dotazniky"][0]["odpovedi"][0]["otazka_id"] == "pocit"
    assert "Aktualizováno" in html(demo)
    # New login reads the same persisted tasks, not a browser-only flag.
    demo.client.post("/patient/logout")
    demo.client.post("/patient", data={"patient_id": "synthetic"})
    assert "Aktualizováno" in html(demo)
    with app.app_context():
        from web.patient_store import load_patient

        view = build_portal(load_patient("synthetic"), demo.at)
        assert view["assessment"] == checkin_assessments(load_patient("synthetic"))[-1]


def test_measurement_control_uses_existing_triage_and_report(demo):
    baseline(demo)
    response = demo.client.post(
        "/patient", data={"follow_up": "teplota_c"}, follow_redirects=True
    )
    assert "tělesná teplota" in response.get_data(as_text=True)
    text = "Právě jsem naměřil 36,8 °C."
    demo.findings[text] = [finding(text, "temperature", value=36.8, unit="degC")]
    post(demo, text)
    saved = finish(demo)
    assert saved["vitalni_funkce"]["teplota_c"]["hodnota"] == 36.8
    view = build_portal(json.loads(demo.path.read_text()), demo.at)
    control = next(c for c in view["controls"] if c["id"] == "teplota_c")
    assert control["value"] == "36.8 °C"
    assert control["status"] == "Aktualizováno"
    assert view["assessment"]["color"] == saved["triage_assessment"]["color"]
    assert "36.8" in demo.client.get("/patients/synthetic/report").get_data(
        as_text=True
    )


def test_new_danger_during_a_control_keeps_immediate_notice(demo):
    baseline(demo)
    demo.client.post("/patient", data={"follow_up": "teplota_c"})
    text = "Jsem náhle zmatený."
    demo.findings[text] = [finding(text, "confusion")]
    response = post(demo, text)
    assert response.status_code == 200
    page = html(demo)
    assert "Naléhavé doporučení" in page
    assert "Volejte ihned 155" in page
    assert not demo.path.exists()
    assert not demo.targeted_calls


def test_failed_control_processing_preserves_the_receipt_without_completing(
    demo, monkeypatch
):
    baseline(demo)
    demo.client.post("/patient", data={"follow_up": "nezadouci_ucinky/pocit"})

    def fail(_):
        raise APIError("Synthetic failure")

    monkeypatch.setattr("web.app.MasterExtractor", lambda _, **kwargs: fail)
    response = post(demo, "Nevím, jak stav popsat.")
    assert "Zpráva je uložená, zpracování se nezdařilo" in response.get_data(
        as_text=True
    )
    assert sessions[demo.key]["received_message"].question == "Jak se celkově cítíte?"
    assert sessions[demo.key]["contact"] is None
    assert not demo.path.exists()
    assert "Aktualizováno" not in html(demo)
    response = demo.client.post("/patient", data={"follow_up": "teplota_c"})
    assert "dokončete nebo ukončete" in response.get_data(as_text=True)
    assert sessions[demo.key]["received_message"].question == "Jak se celkově cítíte?"


def test_conflicting_measurements_do_not_complete_a_control(demo):
    baseline(demo)
    demo.client.post("/patient", data={"follow_up": "teplota_c"})
    text = "Právě naměřeno 36,8 °C i 37,4 °C, nevím, co platí."
    demo.findings[text] = [
        finding(text, "temperature", value=v, unit="degC") for v in (36.8, 37.4)
    ]
    post(demo, text)
    saved = finish(demo)
    assert saved["vitalni_funkce"]["teplota_c"]["hodnota"] is None
    controls = json.loads(demo.path.read_text())["portal_controls"]
    assert (
        next(c for c in controls if c["id"] == "teplota_c")["completed_checkin_id"]
        is None
    )
    view = build_portal(json.loads(demo.path.read_text()), demo.at)
    control = next(c for c in view["controls"] if c["id"] == "teplota_c")
    assert control["value"] is None
    assert control["status"] == "K upřesnění"


def test_unknown_or_overlapping_control_cannot_replace_the_current_contact(demo):
    baseline(demo)
    response = demo.client.post("/patient", data={"follow_up": "foreign/question"})
    assert "není součástí vašeho sledování" in response.get_data(as_text=True)
    post(demo, "Zpráva bez odpovídající otázky")
    current = sessions[demo.key]["contact"].snapshot()
    response = demo.client.post("/patient", data={"follow_up": "teplota_c"})
    assert "dokončete nebo ukončete" in response.get_data(as_text=True)
    assert sessions[demo.key]["contact"].snapshot() == current


def test_future_data_and_future_completions_are_not_shown(demo):
    initial = baseline(demo)
    controls = controls_for(demo.patient)
    tomorrow = checkin("FUTURE", "2026-10-18", feeling=0, temperature=40)
    demo.patient["checkiny"].append(tomorrow)
    update_controls(demo.patient, controls, tomorrow)
    view = build_portal(demo.patient, demo.at)
    assert view["assessment"]["checkin_id"] == initial["checkin_id"]
    assert all(c["status"] != "Aktualizováno" for c in view["controls"])
    assert "40 °C" not in str(view)


def test_old_measurement_or_null_answer_cannot_complete_a_task(demo):
    baseline(demo)
    controls = controls_for(demo.patient)
    current = checkin("NEW", "2026-10-17", feeling=None, temperature=36.8)
    current["vitalni_funkce"]["teplota_c"]["observed_at"] = "2026-10-15T10:00:00+02:00"
    update_controls(demo.patient, controls, current)
    assert all(c["completed_checkin_id"] is None for c in controls)


def test_only_a_documented_due_time_creates_a_due_reminder(demo):
    baseline(demo)
    controls = controls_for(demo.patient)
    controls[0]["due_at"] = (demo.at - timedelta(minutes=1)).isoformat()
    demo.patient["portal_controls"] = controls
    view = build_portal(demo.patient, demo.at)
    assert view["controls"][0]["status"] == "K doplnění"
    assert view["controls"][1]["due"] is None
