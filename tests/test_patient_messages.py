"""Patient text, questionnaire contradictions and replay, with no network calls."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from llm_intake.client import APIError
from llm_intake.master_contract import Fact, NumericRange
from main import compare_patient
from meddi.messages import evaluate_message_checkin, message_event
from tests.test_form import answer, checkin, questionnaire
from web.app import app


def case(text="Dobre.", *forms):
    raw = checkin(*forms)
    raw.update(
        checkin_id="C1",
        patient_id="synthetic-patient",
        vyplnil="pacient",
        zprava_pacienta=text,
        vitalni_funkce={},
        prilohy=[],
    )
    return {"patient_id": "synthetic-patient", "checkiny": [raw]}, raw


def fact(concept, evidence, value=None, **kwargs):
    return Fact(concept, "present", evidence, "patient", value=value, **kwargs)


def no_effects():
    return questionnaire(
        "nezadouci_ucinky",
        answer("pocit", "2", 1),
        answer("ucinky", ["Nemám žádné nežádoucí účinky"], [12]),
    )


def test_slovak_diarrhea_is_added_without_inventing_baseline_or_window():
    text = "od vcera mam hnacku asi 6 krat, slaby som"
    patient, raw = case(text, no_effects())
    patient["lecba"] = {"leky": ["irinotekan"], "cykly": [{"datum_d1": "2026-10-15"}]}
    extractor = Mock(
        return_value=[
            fact(
                "diarrhea.episodes",
                text,
                6,
                unit="episodes",
                time_text="od vcera",
                certainty="approximate",
            )
        ]
    )
    before = deepcopy(patient)
    result = evaluate_message_checkin(patient, raw, extract=extractor)
    assert result["message_analysis_status"] == "complete"
    assert result["color"] in {"yellow", "orange", "red"}
    assert extractor.call_count == 1
    assert extractor.call_args.args[0].source == "patient_message"
    inputs = result["triage_inputs"]
    assert inputs["observations"]["diarrhea"][0]["value"] is True
    assert "stools_above_baseline_24h" not in inputs["observations"]
    assert "hours_without_diarrhea" not in inputs["observations"]
    assert result["message_conflicts"][0]["question_id"] == "ucinky"
    assert any("obvyklému" in q for q in result["follow_up_questions"])
    assert patient == before


def test_message_omission_is_not_a_questionnaire_denial():
    patient, raw = case(
        "Mám průjem.", questionnaire("nezadouci_ucinky", answer("pocit", "2", 1))
    )
    result = evaluate_message_checkin(
        patient, raw, extract=lambda _: [fact("diarrhea", raw["zprava_pacienta"])]
    )
    assert result["message_analysis_status"] == "complete"
    assert not result["message_conflicts"]


def test_high_fever_message_wins_over_low_temperature_choice():
    patient, raw = case(
        "Dnes mám 38.5 stupně.",
        questionnaire("nezadouci_ucinky", answer("teplota", "37–37.9", 0)),
    )
    patient["lecba"] = {"leky": ["5-FU"], "cykly": [{"datum_d1": "2026-10-15"}]}
    result = evaluate_message_checkin(
        patient, raw, extract=lambda _: [fact("temperature", "38.5", 38.5, unit="degC")]
    )
    assert result["color"] == "red"
    assert result["message_conflicts"][0]["field"] == "temperature_c"
    assert result["follow_up_questions"]
    assert any(r["rule_id"] == "fever" for r in result["reasons"])


def test_reassuring_text_does_not_cancel_a_structured_red_rule():
    patient, raw = case(
        "Nezvracím.",
        questionnaire("nezadouci_ucinky", answer("zvraceni", "Více než 5", 2)),
    )
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [Fact("vomiting", "absent", "Nezvracím", "patient")],
    )
    assert result["color"] == "red"
    assert result["message_conflicts"][0]["question_id"] == "zvraceni"


def test_reassuring_message_is_not_automatically_an_unassessed_message():
    patient, raw = case("Dobre.", no_effects())
    result = evaluate_message_checkin(patient, raw, extract=lambda _: [])
    assert result["color"] == "green"
    assert not any(
        i["code"] == "unassessed_patient_message" for i in result["review_issues"]
    )


@pytest.mark.parametrize("text", [None, "", "  "])
def test_empty_message_never_calls_model(text):
    patient, raw = case(text, no_effects())
    extractor = Mock(side_effect=AssertionError("must not call"))
    assert (
        evaluate_message_checkin(patient, raw, extract=extractor)[
            "message_analysis_status"
        ]
        == "not_present"
    )
    extractor.assert_not_called()


@pytest.mark.parametrize("failure", [APIError("unavailable"), ValueError("bad schema")])
def test_failed_extraction_is_visible_and_cannot_downgrade_known_red(failure):
    patient, raw = case(
        "Zpráva.",
        questionnaire("nezadouci_ucinky", answer("bol_hrud", "Nová bolest", 1)),
    )
    result = evaluate_message_checkin(patient, raw, extract=Mock(side_effect=failure))
    assert result["color"] == "red"
    assert result["message_analysis_status"] == "failed"
    assert any(i["code"] == "message_analysis_failed" for i in result["review_issues"])


def test_fabricated_quote_is_rejected_and_original_kept_for_review():
    patient, raw = case("Dobre.", no_effects())
    result = evaluate_message_checkin(
        patient, raw, extract=lambda _: [fact("new_chest_pain", "Never said")]
    )
    assert result["message_analysis_status"] == "failed"
    assert result["color"] == "yellow"


def test_cached_analysis_is_reused_and_changed_source_is_rejected():
    patient, raw = case("Dobre.", no_effects())
    first = evaluate_message_checkin(patient, raw, extract=lambda _: [])
    extractor = Mock(side_effect=AssertionError("must reuse"))
    again = evaluate_message_checkin(
        patient, raw, analysis=first["message_analysis"], extract=extractor
    )
    assert again["color"] == "green"
    assert again["message_analysis_status"] == "complete"
    extractor.assert_not_called()
    raw["zprava_pacienta"] = "Nová zpráva."
    assert (
        evaluate_message_checkin(patient, raw, analysis=first["message_analysis"])[
            "message_analysis_status"
        ]
        == "failed"
    )


def test_caregiver_symptoms_are_not_assigned_to_patient():
    patient, raw = case("Dcera píše: já mám bolesti na hrudi.", no_effects())
    raw["vyplnil"] = "dcera"
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [
            Fact("new_chest_pain", "present", "já mám bolesti na hrudi", "caregiver")
        ],
    )
    assert message_event(raw).author == "caregiver"
    assert result["color"] == "yellow"  # Separate review, no fabricated patient red.
    assert not result["message_conflicts"]


def test_original_message_only_reaches_extractor_not_future_or_references():
    patient, raw = case("Dobre.", no_effects())
    patient.update(nazev_scenare="FORBIDDEN", ground_truth="FORBIDDEN")
    patient["checkiny"].append(
        {
            **deepcopy(raw),
            "checkin_id": "future",
            "datum": "2027-01-01",
            "zprava_pacienta": "FORBIDDEN",
        }
    )
    extractor = Mock(return_value=[])
    result = evaluate_message_checkin(patient, raw, extract=extractor)
    assert "FORBIDDEN" not in str(extractor.call_args)
    assert "FORBIDDEN" not in str(result)
    assert result["color"] == "green"


def test_message_event_uses_prague_daylight_saving_independent_of_machine():
    _, raw = case()
    assert message_event(raw).available_at.endswith("+02:00")
    raw["datum"] = "2026-12-01"
    assert message_event(raw).available_at.endswith("+01:00")


@pytest.mark.parametrize("hours", [12, 24])
def test_explicit_symptom_free_duration_is_not_mistaken_for_old_observation(hours):
    text = f"Jsem {hours} hodin bez průjmu."
    patient, raw = case(text, no_effects())
    patient["lecba"] = {"leky": ["irinotekan"], "cykly": [{"datum_d1": "2026-10-15"}]}
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [
            fact(
                "hours_without_diarrhea",
                text,
                hours,
                unit="hours",
                time_text=f"{hours} hodin",
            )
        ],
    )
    assert result["message_analysis_status"] == "complete"
    assert (
        result["triage_inputs"]["observations"]["hours_without_diarrhea"][0]["value"]
        == hours
    )
    assert not result["unprocessed_facts"]
    assert not result["message_conflicts"]


def test_past_timestamp_is_not_mistaken_for_a_duration():
    text = "Před 12 hodinami byl průjem."
    patient, raw = case(text, no_effects())
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [
            fact(
                "hours_without_diarrhea",
                text,
                12,
                unit="hours",
                time_text="Před 12 hodinami",
            )
        ],
    )
    assert "hours_without_diarrhea" not in result["triage_inputs"]["observations"]
    assert result["unprocessed_facts"]


def test_comparison_references_never_reach_extractor():
    patient, _raw = case("Dobre.", no_effects())
    extractor = Mock(return_value=[])
    result = compare_patient(
        patient,
        [{"checkin_id": "C1", "uroven": 4, "zduvodneni": "FORBIDDEN"}],
        with_messages=True,
        extract=extractor,
    )
    assert result[0]["rules_color"] == "green"
    assert "FORBIDDEN" not in str(extractor.call_args)


@pytest.fixture
def message_web(monkeypatch, tmp_path):
    patient, raw = case("Dobre.", no_effects())
    from web import patient_store

    directory = tmp_path / "data"
    monkeypatch.setitem(app.config, "DATA_DIR", directory)
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "demo")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "synthetic-password")
    monkeypatch.setattr(
        patient_store, "load_source_patient", lambda _: deepcopy(patient)
    )
    monkeypatch.setattr(
        "web.patient_report.list_patient_ids", lambda: [patient["patient_id"]]
    )
    extractor = Mock(return_value=[])
    monkeypatch.setattr(
        "meddi.messages.MasterExtractor", lambda *args, **kwargs: extractor
    )
    monkeypatch.setattr("meddi.messages.Client.from_env", lambda: object())
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Basic ZGVtbzpzeW50aGV0aWMtcGFzc3dvcmQ="
    return client, extractor, patient, raw, directory


def test_web_extracts_once_and_reuses_saved_facts_after_session_loss(message_web):
    client, extractor, patient, raw, directory = message_web
    url = f"/patients/{patient['patient_id']}/report"
    assert client.get(url).status_code == 200
    extractor.assert_not_called()
    with client.session_transaction() as session:
        token = session["message_analysis_csrf"]
    action = f"/patients/{patient['patient_id']}/checkins/C1/analyze-message"
    assert client.post(action, data={"token": token}).status_code == 302
    assert extractor.call_count == 1
    assert (directory / "pacienti/synthetic-patient.json").is_file()
    assert "patient_message_analysis" not in raw
    for _ in range(2):
        response = client.get(url)
        assert response.status_code == 200
        assert "Zpráva již byla zpracována" in response.get_data(as_text=True)
    assert client.post(action, data={"token": token}).status_code == 302
    assert extractor.call_count == 1
    with client.session_transaction() as session:
        session.clear()
    assert client.get(url).status_code == 200
    assert extractor.call_count == 1


def test_web_message_action_needs_auth_and_csrf(message_web):
    client, extractor, *_ = message_web
    action = "/patients/synthetic-patient/checkins/C1/analyze-message"
    assert client.post(action).status_code == 400
    client.environ_base.pop("HTTP_AUTHORIZATION")
    assert client.post(action).status_code == 401
    extractor.assert_not_called()


def test_exact_baseline_increase_conflicts_with_mild_choice_and_keeps_worse_rule():
    text = "Za posledních 24 hodin mám o 6 stolic více než obvykle."
    patient, raw = case(
        text,
        questionnaire("nezadouci_ucinky", answer("prujem", "Do tří nad normál", 0)),
    )
    patient["lecba"] = {"leky": ["irinotekan"], "cykly": [{"datum_d1": "2026-10-15"}]}
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [
            fact(
                "diarrhea.increase_over_baseline",
                text,
                6,
                unit="episodes",
                time_text="Za posledních 24 hodin",
            )
        ],
    )
    assert result["message_analysis_status"] == "complete"
    assert result["color"] == "orange"
    assert any(
        c["field"] == "stools_above_baseline_24h" for c in result["message_conflicts"]
    )
    assert any(
        r["rule_id"] == "high_risk_treatment_diarrhea" for r in result["reasons"]
    )


def test_range_preserves_presence_but_never_becomes_exact_count():
    text = "Mám pět nebo šest průjmových stolic."
    patient, raw = case(text, no_effects())
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [
            fact("diarrhea.episodes", text, NumericRange(5, 6), unit="episodes")
        ],
    )
    assert result["message_analysis_status"] == "complete"
    observations = result["triage_inputs"]["observations"]
    assert observations["diarrhea"][0]["value"] is True
    assert "stools_above_baseline_24h" not in observations
    assert result["follow_up_questions"]


def test_past_message_does_not_create_a_current_conflict():
    text = "Minulý týden jsem měl průjem."
    patient, raw = case(text, no_effects())
    result = evaluate_message_checkin(
        patient,
        raw,
        extract=lambda _: [fact("diarrhea", text, time_text="Minulý týden")],
    )
    assert not result["message_conflicts"]
    assert "diarrhea" not in result["triage_inputs"]["observations"]
    assert result["unprocessed_facts"][0]["reason"] == "unresolved_observation_time"


def test_web_api_failure_is_visible_and_does_not_save_success(message_web):
    client, extractor, patient, _raw, directory = message_web
    extractor.side_effect = APIError("unavailable")
    client.get(f"/patients/{patient['patient_id']}/report")
    with client.session_transaction() as session:
        token = session["message_analysis_csrf"]
    response = client.post(
        "/patients/synthetic-patient/checkins/C1/analyze-message", data={"token": token}
    )
    assert response.status_code == 502
    assert "Zprávu se nepodařilo vyhodnotit" in response.get_data(as_text=True)
    assert not (directory / "pacienti/synthetic-patient.json").exists()


def test_extraction_payload_uses_same_client_and_only_message_data():
    from llm_intake.client import Client
    from llm_intake.master import MasterExtractor
    from meddi.clinical_rules import OBSERVATION_FLAGS, OBSERVATION_NUMBERS

    _, raw = case("Mám novou bolest na hrudi.")
    payload = MasterExtractor(
        Client("synthetic-key"),
        clinical_fields=sorted(OBSERVATION_FLAGS | OBSERVATION_NUMBERS),
    ).payload(message_event(raw))
    import json

    data = json.loads(payload["messages"][-1]["content"])
    assert "new_chest_pain" in data["clinical_fields"]
    assert set(data["message"]) == {"text", "question", "author"}
    assert data["message"]["text"] == raw["zprava_pacienta"]
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert (
        "triage"
        not in payload["response_format"]["json_schema"]["schema"]["properties"]
    )


def test_onc018_c03_adds_slovak_message_findings_without_references():
    from meddi.loader import load_patient

    patient = load_patient("ONC-018")
    raw = next(c for c in patient["checkiny"] if c["checkin_id"] == "ONC-018-C03")
    text = raw["zprava_pacienta"]
    extractor = Mock(
        return_value=[
            fact(
                "diarrhea.episodes",
                text,
                6,
                unit="episodes",
                time_text="od vcera",
                certainty="approximate",
            ),
            fact("fatigue", "slaby som"),
        ]
    )
    result = evaluate_message_checkin(patient, raw, extract=extractor)
    assert result["message_analysis_status"] == "complete"
    assert result["triage_inputs"]["observations"]["diarrhea"][0]["value"] is True
    assert result["follow_up_questions"]
    assert "stools_above_baseline_24h" not in result["triage_inputs"]["observations"]
    assert any(
        r["rule_id"] == "irinotecan_diarrhea_not_resolved" for r in result["reasons"]
    )
    assert not result["message_conflicts"]


def test_cli_with_messages_uses_same_extraction_and_prints_followup(
    monkeypatch, capsys
):
    import main

    patient, raw = case("Mám průjem.", no_effects())
    monkeypatch.setattr(main, "load_patient", lambda _: patient)
    monkeypatch.setattr(
        main, "load_ground_truth", lambda _: [{"checkin_id": "C1", "uroven": 2}]
    )
    monkeypatch.setattr("meddi.messages.Client.from_env", lambda: object())
    extractor = Mock(return_value=[fact("diarrhea", raw["zprava_pacienta"])])
    monkeypatch.setattr(
        "meddi.messages.MasterExtractor", lambda *args, **kwargs: extractor
    )
    monkeypatch.setattr(
        "sys.argv", ["main.py", "synthetic-patient", "--with-messages", "--details"]
    )
    main.main()
    output = capsys.readouterr().out
    assert "Message: complete" in output
    assert "Follow-up:" in output
    assert extractor.call_count == 1


@pytest.mark.parametrize("arguments", [[], ["synthetic-patient"]])
def test_default_cli_uses_message_and_can_change_color_without_a_switch(
    monkeypatch, capsys, arguments
):
    import main

    patient, raw = case("Mám novou bolest na hrudi.", no_effects())
    monkeypatch.setattr(main, "list_patient_ids", lambda: [patient["patient_id"]])
    monkeypatch.setattr(main, "load_patient", lambda _: patient)
    monkeypatch.setattr(
        main, "load_ground_truth", lambda _: [{"checkin_id": "C1", "uroven": 4}]
    )
    monkeypatch.setattr("meddi.messages.Client.from_env", lambda: object())
    extractor = Mock(return_value=[fact("new_chest_pain", raw["zprava_pacienta"])])
    monkeypatch.setattr(
        "meddi.messages.MasterExtractor", lambda *args, **kwargs: extractor
    )
    monkeypatch.setattr("sys.argv", ["main.py", *arguments])
    assert main.main() == 0
    output = capsys.readouterr().out
    assert "red" in output
    assert "complete=1; failed=0" in output
    assert extractor.call_count == 1
    baseline = compare_patient(
        patient, [{"checkin_id": "C1", "uroven": 4}], with_messages=False
    )
    assert baseline[0]["rules_color"] == "yellow"


def test_default_cli_reports_missing_key_without_details_and_returns_failure(
    monkeypatch, capsys
):
    import main

    patient, _ = case("Dobre.", no_effects())
    monkeypatch.setattr(main, "load_patient", lambda _: patient)
    monkeypatch.setattr(
        main, "load_ground_truth", lambda _: [{"checkin_id": "C1", "uroven": 1}]
    )
    monkeypatch.setattr(
        "meddi.messages.Client.from_env",
        Mock(side_effect=ValueError("Chybí MEDDI_LLM_API_KEY.")),
    )
    monkeypatch.setattr("sys.argv", ["main.py", "synthetic-patient"])
    assert main.main() == 1
    captured = capsys.readouterr()
    assert "complete=0; failed=1" in captured.out
    assert "failed" in captured.out
    assert "MEDDI_LLM_API_KEY" in captured.err
    assert "záložní" in captured.err


def test_offline_switch_skips_model_explicitly(monkeypatch, capsys):
    import main

    patient, _ = case("Mám novou bolest na hrudi.", no_effects())
    monkeypatch.setattr(main, "load_patient", lambda _: patient)
    monkeypatch.setattr(
        main, "load_ground_truth", lambda _: [{"checkin_id": "C1", "uroven": 1}]
    )
    client = Mock(side_effect=AssertionError("offline must not call client"))
    monkeypatch.setattr("meddi.messages.Client.from_env", client)
    monkeypatch.setattr(
        "sys.argv", ["main.py", "synthetic-patient", "--without-messages"]
    )
    assert main.main() == 0
    assert "not_requested=1" in capsys.readouterr().out
    client.assert_not_called()
