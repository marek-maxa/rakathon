"""M3: synthetic patient-to-card scenarios; model/SMTP are never contacted."""

import json
import re
from base64 import b64encode
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from llm_intake.client import APIError, Client
from llm_intake.dialogue import DETAIL_QUESTION
from llm_intake.master_contract import Fact
from web.app import app, sessions


@pytest.fixture
def demo(monkeypatch, tmp_path):
    state = SimpleNamespace(
        at=datetime.fromisoformat("2026-10-17T10:00:00+02:00"),
        patient={
            "patient_id": "synthetic",
            "demografie": {"jmeno_fiktivni": "Synthetic Person"},
            "checkiny": [],
        },
        findings={},
        answers={},
        targeted_calls=[],
        general_calls=[],
    )

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return state.at.astimezone(tz or UTC)

    class Model:
        def extract_events(self, question, sources, questions, events):
            state.targeted_calls.append((question.id, deepcopy(events)))
            if events[-1]["source"] == "master_question":
                return {
                    "status": "unclear",
                    "value": None,
                    "source_index": None,
                    "evidence": None,
                    "follow_up": question.text,
                }
            value = state.answers.get(question.id, 0)
            return {
                "status": "answered",
                "value": value,
                "source_index": len(sources) - 1,
                "evidence": sources[-1],
                "follow_up": None,
            }

    def extract(message):
        state.general_calls.append(message)
        return deepcopy(state.findings.get(message.text, []))

    monkeypatch.setattr("web.app.datetime", Clock)
    monkeypatch.setattr("web.app.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.app.load_patient", lambda _: deepcopy(state.patient))
    monkeypatch.setattr(
        "web.patient_store.load_source_patient", lambda _: deepcopy(state.patient)
    )
    monkeypatch.setattr("web.app.MasterExtractor", lambda _, **kwargs: extract)
    monkeypatch.setattr(Client, "from_env", Model)
    monkeypatch.setitem(app.config, "DATA_DIR", tmp_path)
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "demo")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "synthetic-password")
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = (
        "Basic " + b64encode(b"demo:synthetic-password").decode()
    )
    client.post("/patient", data={"patient_id": "synthetic"})
    with client.session_transaction() as browser_session:
        state.key = browser_session["id"]
    state.client, state.path = client, tmp_path / "pacienti/synthetic.json"
    yield state
    sessions.pop(state.key, None)


def post(demo, text):
    html = demo.client.get("/patient").get_data(as_text=True)
    token = re.search(r'name="submission_token" value="([^"]+)"', html)[1]
    return demo.client.post(
        "/patient",
        data={"answer": text, "submission_token": token},
        follow_redirects=True,
    )


def finding(
    text,
    concept,
    value=None,
    *,
    unit=None,
    presence="present",
    subject="patient",
    time_text=None,
):
    return Fact(
        concept, presence, text, subject, value=value, unit=unit, time_text=time_text
    )


def finish(demo):
    for _ in range(10):
        contact = sessions[demo.key]["contact"]
        if contact.state == "paused":
            assert "Naléhavé doporučení" in demo.client.get("/patient").get_data(
                as_text=True
            )
            demo.client.post("/patient", data={"continue": "1"})
        elif contact.state == "needs_description":
            post(demo, "Nevím, jak to přesněji popsat.")
        elif contact.state in {"needs_answer", "needs_correction"}:
            q = contact.active.question
            value = demo.answers.get(q.id, 0)
            text = q.options[value] if q.kind == "jedna" else str(value)
            post(demo, text)
        else:
            break
    else:
        pytest.fail("MVP question budget did not terminate the conversation")
    response = demo.client.post(
        "/patient", data={"confirm": "1"}, follow_redirects=True
    )
    assert "Odpovědi jsou uložené." in response.get_data(as_text=True)
    saved = json.loads(demo.path.read_text(encoding="utf-8"))["checkiny"][-1]
    assert saved["triage_assessment"]["intake"]["dialogue"]["questions_asked"] <= 6
    result = saved["triage_assessment"]
    assert "MUST_NOT_ENTER" not in str(result)
    # Both views use the saved assessment, rather than another model decision.
    report = demo.client.get("/patients/synthetic/report").get_data(as_text=True)
    assert saved["checkin_id"] in report
    assert result["doporuceny_kontakt"] in report
    team = demo.client.get("/team").get_data(as_text=True)
    if result["upozornit_tym"]:
        assert saved["checkin_id"] in team
    return saved


@pytest.mark.parametrize("text", ["dobrý", "Dobře.", "dobre"])
@pytest.mark.parametrize("model_finds_state", [False, True])
@pytest.mark.parametrize("rating", [1, 2])
def test_reassuring_master_is_clarified_once_and_reaches_green(
    demo, text, model_finds_state, rating
):
    if model_finds_state:
        demo.findings[text] = [finding(text, "overall_feeling", text)]
    demo.answers["pocit"] = rating - 1  # Source options use zero-based indices.
    post(demo, text)
    contact = sessions[demo.key]["contact"]
    assert contact.state == "needs_answer"
    assert contact.active.question.id == "pocit"
    assert demo.targeted_calls == []  # No ordinal guessed from the opening.
    saved = finish(demo)
    result = saved["triage_assessment"]
    assert result["color"] == "green"
    assert result["doporuceny_krok"] == "dalsi_sledovani"
    assert not result["upozornit_tym"]
    assert len(demo.targeted_calls) == 1
    assert len(result["clarified_facts"]) == 1
    assert not result["unprocessed_facts"]
    assert saved["zprava_pacienta"] == text
    assert result["intake"]["facts"][0]["value"] == text
    assert not result["intake"]["dialogue"]["message_specificity"]["needs_details"]
    assert result["intake"]["dialogue"]["message_specificity"]["attempts"] == 0


@pytest.mark.parametrize("opening", ["blbě", "špatně", "dobře"])
@pytest.mark.parametrize("model_finds_state", [False, True])
def test_general_state_four_requests_details_then_routes_the_actual_symptom(
    demo, opening, model_finds_state
):
    if model_finds_state:
        demo.findings[opening] = [finding(opening, "overall_feeling", opening)]
    demo.answers["pocit"] = 3
    post(demo, opening)
    response = post(demo, "4")
    contact = sessions[demo.key]["contact"]
    assert contact.state == "needs_description"
    assert DETAIL_QUESTION in response.get_data(as_text=True)
    assert contact.snapshot()["dialogue"]["message_specificity"]["needs_details"]
    assert not demo.path.exists()
    demo.client.post("/patient", data={"confirm": "1"})
    assert not demo.path.exists()  # A score alone cannot finish this contact.

    detail = "Jsem unavený, odpočinek mi pomáhá."
    demo.findings[detail] = [finding(detail, "fatigue")]
    demo.answers["unava"] = 0
    response = post(demo, detail)
    assert detail in response.get_data(as_text=True)  # Visible in shared review.
    result = finish(demo)["triage_assessment"]
    specificity = result["intake"]["dialogue"]["message_specificity"]
    assert not specificity["needs_details"] and specificity["attempts"] == 1
    details_event = result["intake"]["messages"][-1]
    assert details_event["question"] == DETAIL_QUESTION
    assert details_event["text"] == detail
    assert result["intake"]["facts"][-1]["source_message_id"] == details_event["id"]
    assert [
        a["question"]["question_id"] for a in result["intake"]["question_answers"]
    ] == ["pocit", "unava"]


def test_repeatedly_vague_description_stops_with_review_not_green(demo):
    demo.answers["pocit"] = 3
    post(demo, "blbě")
    post(demo, "4")
    result = finish(demo)["triage_assessment"]
    status = result["intake"]["dialogue"]
    assert status["state"] == "unresolved"
    assert status["reason"] == "insufficient_detail"
    assert status["message_specificity"]["needs_details"]
    assert status["message_specificity"]["attempts"] == 2
    assert status["questions_asked"] == 4
    assert result["requires_review"] and result["color"] != "green"


def test_reassuring_paraphrase_with_low_score_does_not_request_more_description(demo):
    opening = "Dnes se cítím celkem dobře."
    demo.findings[opening] = [finding(opening, "overall_feeling", opening)]
    demo.answers["pocit"] = 1
    post(demo, opening)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "green"
    assert result["intake"]["dialogue"]["message_specificity"]["attempts"] == 0


def test_description_extraction_failure_keeps_receipt_and_does_not_close_contact(
    demo, monkeypatch
):
    demo.answers["pocit"] = 3
    post(demo, "blbě")
    post(demo, "4")
    contact = sessions[demo.key]["contact"]
    before = contact.snapshot()

    def fail(_):
        raise APIError("synthetic description extraction failure")

    monkeypatch.setattr(contact, "_extract_message", fail)
    html = post(demo, "Je mi pořád nějak špatně.").get_data(as_text=True)
    stored = sessions[demo.key]
    assert "Zpráva je uložená, zpracování se nezdařilo" in html
    assert stored["contact"].snapshot() == before
    assert stored["contact"].state == "needs_description"
    assert stored["received_message"].question == DETAIL_QUESTION
    assert not stored["done"] and not demo.path.exists()


def test_urgent_finding_in_description_pauses_before_targeted_extraction(demo):
    demo.answers["pocit"] = 3
    post(demo, "blbě")
    post(demo, "4")
    calls_before = len(demo.targeted_calls)
    detail = "Teď mám novou bolest na hrudi."
    demo.findings[detail] = [finding(detail, "new_chest_pain")]
    html = post(demo, detail).get_data(as_text=True)
    assert sessions[demo.key]["contact"].state == "paused"
    assert "Naléhavé doporučení" in html and "155" in html
    assert len(demo.targeted_calls) == calls_before
    assert finish(demo)["triage_assessment"]["color"] == "red"


def test_description_respects_total_question_budget(demo, monkeypatch):
    monkeypatch.setitem(app.config, "MAX_QUESTIONS", 2)
    demo.answers["pocit"] = 3
    post(demo, "blbě")
    post(demo, "4")
    result = finish(demo)["triage_assessment"]
    status = result["intake"]["dialogue"]
    assert status["state"] == "limited" and status["questions_asked"] == 2
    assert status["message_specificity"]["needs_details"]
    assert result["requires_review"] and result["color"] != "green"


@pytest.mark.parametrize("text", ["Nevím.", "OK", "Dobrý, ale špatně dýchám."])
def test_missing_or_mixed_information_is_not_a_blanket_green(demo, text):
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "yellow"
    assert result["requires_review"]
    assert not result["clarified_facts"]


def test_qualitative_confirmation_does_not_erase_a_red_finding(demo):
    text = "Dobrý, ale jsem zmatený."
    demo.findings[text] = [
        finding(text, "overall_feeling", "dobrý"),
        finding(text, "confusion"),
    ]
    demo.answers["pocit"] = 1
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "red"
    assert len(result["clarified_facts"]) == 1
    assert any(r["rule_id"] == "neurological_red_flags" for r in result["reasons"])


def test_fever_after_treatment_from_patient_to_card(demo):
    demo.patient["lecba"] = {
        "leky": ["doxorubicin"],
        "cykly": [{"datum_d1": "2026-10-07"}],
    }
    text = "Dnes mám teplotu 38,2 °C."
    demo.findings[text] = [finding(text, "temperature", 38.2, unit="degC")]
    demo.answers["teplota"] = 1
    post(demo, text)
    assert demo.targeted_calls == []
    saved = finish(demo)
    assert saved["triage_assessment"]["color"] == "red"
    assert saved["vitalni_funkce"]["teplota_c"]["hodnota"] == 38.2
    source = saved["triage_assessment"]["triage_inputs"]["prepared"]["context_sources"]
    assert (
        source["chemotherapy_within_6_weeks"]["source"]["cycles"][0]["datum_d1"]
        == "2026-10-07"
    )


def test_two_day_immunotherapy_diarrhea_and_current_improvement(demo):
    demo.patient["lecba"] = {"leky": ["nivolumab"]}
    results = []
    for day, count, pain in [(17, 2, False), (18, 5, True), (19, 2, False)]:
        if results:
            demo.client.post("/patient", data={"restart": "1"})
        demo.at = datetime.fromisoformat(f"2026-10-{day}T10:00:00+02:00")
        text = (
            f"Za posledních 24 hodin mám {count} průjmové stolice nad svůj normál. "
            + ("Bolí mě břicho." if pain else "Břicho nebolí.")
        )
        demo.findings[text] = [
            finding(
                text,
                "diarrhea.increase_over_baseline",
                count,
                unit="stools",
                time_text="Za posledních 24 hodin",
            ),
            finding(text, "abdominal_pain", presence="present" if pain else "absent"),
        ]
        demo.answers["prujem"] = 1 if count >= 4 else 0
        post(demo, text)
        results.append(finish(demo)["triage_assessment"])
    assert [r["minimum_color"] for r in results] == ["yellow", "orange", "yellow"]
    assert not any(r["color"] == "red" for r in results)
    assert not any(r["color"] == "orange" for r in results[-1]["reasons"])


def test_weight_trend_then_orthopnea_uses_current_available_history(demo):
    demo.patient["lecba"] = {"leky": ["trastuzumab"]}
    demo.patient["checkiny"] = [
        {
            "patient_id": "synthetic",
            "checkin_id": "baseline",
            "datum": "2026-10-14",
            "cas": "10:00",
            "stav": "vyplneno",
            "dotazniky": [],
            "vitalni_funkce": {"vaha_kg": {"hodnota": 70}},
        }
    ]
    first = "Dnes vážím 72,5 kg a mám oteklé nohy."
    demo.findings[first] = [finding(first, "weight_kg", 72.5, unit="kg")]
    post(demo, first)
    result = finish(demo)["triage_assessment"]
    assert result["minimum_color"] == "yellow"
    assert (
        result["triage_inputs"]["observations"]["weight_gain_3_days_kg"][0]["value"]
        == 2.5
    )
    demo.client.post("/patient", data={"restart": "1"})
    demo.at = datetime.fromisoformat("2026-10-18T10:00:00+02:00")
    second = "Nově musím kvůli dýchání spát vsedě."
    demo.findings[second] = [finding(second, "orthopnea", time_text="Nově")]
    post(demo, second)
    assert finish(demo)["triage_assessment"]["minimum_color"] == "orange"


def test_anticoagulation_bleeding_keeps_specific_site_and_ignores_future_drug(demo):
    demo.patient["lecba"] = {"leky": ["kapecitabin"]}
    demo.patient["leky"] = [
        {"lek": "warfarin", "od_data": "2026-10-01"},
        {"lek": "MUST_NOT_ENTER", "od_data": "2026-10-20"},
    ]
    text = "Mám krev ve stolici."
    demo.findings[text] = [finding(text, "blood_in_stool")]
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "red"
    source = result["triage_inputs"]["prepared"]["context_sources"]
    assert source["anticoagulation"]["source"]["drugs"][0]["name"] == "warfarin"
    assert result["triage_inputs"]["observations"]["blood_in_stool"][0]["value"] is True
    assert "blood_in_urine" not in result["triage_inputs"]["observations"]


def test_caregiver_and_palliative_context_remain_separate_from_patient_symptoms(demo):
    demo.patient["lecba"] = {"zamer": "symptomatická paliativní péče"}
    html = demo.client.post(
        "/patient", data={"set_author": "1", "caregiver": "1"}, follow_redirects=True
    ).get_data(as_text=True)
    assert "Jak se dnes cítí pacient, za kterého odpovídáte?" in html
    text = "Maminka je bez nových potíží. Já už jsem jako pečující vyčerpaná."
    demo.findings[text] = [finding(text, "caregiver_exhaustion", subject="caregiver")]
    post(demo, text)
    saved = finish(demo)
    result = saved["triage_assessment"]
    assert saved["vyplnil"] == "pecujici"
    assert result["intake"]["message"]["author"] == "caregiver"
    assert result["minimum_color"] == "yellow"
    assert result["triage_inputs"]["context"]["palliative_care"] is True
    assert result["routing"]["contact_code"] == "palliative_team_24h"
    assert "155" in result["doporuceny_kontakt"]
    assert "fatigue" not in result["triage_inputs"]["observations"]


def test_milder_questionnaire_choice_cannot_remove_opening_fever(demo):
    demo.patient["lecba"] = {"leky": ["5-FU"], "cykly": [{"datum_d1": "2026-10-15"}]}
    text = "Dnes mám 38,5 °C."
    demo.findings[text] = [finding(text, "temperature", 38.5, unit="degC")]
    demo.answers["teplota"] = 0
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["minimum_color"] == "red"
    assert any(i["code"] == "conflicting_temperature" for i in result["review_issues"])
    assert result["intake"]["question_answers"][0]["confirmed"]


@pytest.mark.parametrize("temperature,color", [(37.9, "green"), (38, "red")])
def test_fever_boundary_does_not_turn_every_post_chemo_contact_red(
    demo, temperature, color
):
    demo.patient["lecba"] = {
        "leky": ["doxorubicin"],
        "cykly": [{"datum_d1": "2026-10-07"}],
    }
    text = f"Celkový pocit 2 z 5, teplota {temperature} °C."
    demo.findings[text] = [
        finding(text, "overall_feeling", 2),
        finding(text, "temperature", temperature, unit="degC"),
    ]
    demo.answers.update(pocit=1, teplota=0 if temperature < 38 else 1)
    post(demo, text)
    assert finish(demo)["triage_assessment"]["color"] == color


@pytest.mark.parametrize("count,color", [(3, "yellow"), (4, "orange")])
def test_immunotherapy_diarrhea_boundary_without_abdominal_pain(demo, count, color):
    demo.patient["lecba"] = {"leky": ["nivolumab"]}
    text = f"Za posledních 24 hodin mám {count} průjmové stolice nad normál, břicho nebolí."
    demo.findings[text] = [
        finding(
            text,
            "diarrhea.increase_over_baseline",
            count,
            unit="stools",
            time_text="Za posledních 24 hodin",
        ),
        finding(text, "abdominal_pain", presence="absent"),
    ]
    demo.answers["prujem"] = 0 if count == 3 else 1
    post(demo, text)
    assert finish(demo)["triage_assessment"]["minimum_color"] == color


def test_weight_gain_at_boundary_does_not_trigger_cardiotoxic_rule(demo):
    demo.patient["lecba"] = {"leky": ["trastuzumab"]}
    demo.patient["checkiny"] = [
        {
            "patient_id": "synthetic",
            "checkin_id": "baseline",
            "datum": "2026-10-14",
            "cas": "10:00",
            "stav": "vyplneno",
            "dotazniky": [],
            "vitalni_funkce": {"vaha_kg": {"hodnota": 70}},
        }
    ]
    text = "Pocit 2 z 5, dnes vážím 72 kg."
    demo.findings[text] = [
        finding(text, "overall_feeling", 2),
        finding(text, "weight_kg", 72, unit="kg"),
    ]
    demo.answers["pocit"] = 1
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "green"
    assert not result["unresolved_concepts"]
    assert result["intake"]["unmapped_concepts"] == ["weight_kg"]
    assert not any(
        r["rule_id"] == "cardiotoxic_edema_or_weight_gain" for r in result["reasons"]
    )


@pytest.mark.parametrize("active,color", [(False, "green"), (True, "orange")])
def test_new_bruises_respect_drug_availability_without_inventing_critical_bleeding(
    demo, active, color
):
    demo.patient["lecba"] = {"leky": ["kapecitabin"]}
    demo.patient["leky"] = [
        {"lek": "warfarin", "od_data": "2026-10-01" if active else "2026-10-20"}
    ]
    text = (
        "Celkový pocit 2 z 5, nemám žádné nové modřiny."
        if not active
        else "Celkový pocit 2 z 5, mám nové modřiny."
    )
    demo.findings[text] = [
        finding(text, "overall_feeling", 2),
        finding(text, "new_bruises", presence="present" if active else "absent"),
    ]
    demo.answers["pocit"] = 1
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == color
    assert "blood_in_stool" not in result["triage_inputs"]["observations"]
    assert ("anticoagulation" in result["triage_inputs"]["context"]) == active


def test_palliative_context_never_suppresses_critical_help_and_author_can_change(demo):
    demo.patient["lecba"] = {"zamer": "symptomatická paliativní péče"}
    demo.patient["predem_vyslovena_prani"] = "Syntetické přání zůstat doma."
    text = "Celkový pocit 2 z 5."
    demo.findings[text] = [finding(text, "overall_feeling", 2)]
    demo.answers["pocit"] = 1
    post(demo, text)
    assert sessions[demo.key]["contact"].state == "needs_answer"
    demo.client.post("/patient", data={"set_author": "1", "caregiver": "1"})
    reply = "2"
    demo.findings[reply] = [finding(reply, "confusion")]
    post(demo, reply)
    saved = finish(demo)
    result = saved["triage_assessment"]
    assert result["color"] == "red"
    assert "155" in result["doporuceny_kontakt"]
    assert "urgentní" in result["doporuceny_kontakt"]
    assert saved["zdrojove_zpravy"][0]["author"] == "patient"
    assert saved["zdrojove_zpravy"][1]["author"] == "caregiver"
    assert saved["vyplnil"] == "pacient"
    report = demo.client.get("/patients/synthetic/report").get_data(as_text=True)
    assert "Syntetické přání zůstat doma." in report
    assert "ověřit platnost" in report
    assert "Syntetické přání zůstat doma." not in str(result["triage_inputs"])


def test_matching_temperature_answer_is_not_a_false_conflict(demo):
    text = "Teplota 36,7 °C, celkový pocit 2 z 5."
    demo.findings[text] = [
        finding(text, "temperature", 36.7, unit="degC"),
        finding(text, "overall_feeling", 2),
    ]
    demo.answers.update(teplota=0, pocit=1)
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "green"
    assert not any(
        i["code"] == "conflicting_temperature" for i in result["review_issues"]
    )


@pytest.mark.parametrize(
    "subject,presence", [("unknown", "present"), ("patient", "uncertain")]
)
def test_confirmed_feeling_does_not_hide_unknown_subject_or_uncertain_finding(
    demo, subject, presence
):
    text = "dobrý"
    demo.findings[text] = [
        finding(text, "overall_feeling", "dobrý", subject=subject, presence=presence)
    ]
    demo.answers["pocit"] = 1
    post(demo, text)
    result = finish(demo)["triage_assessment"]
    assert result["color"] == "yellow"
    assert not result["clarified_facts"]
    assert result["unprocessed_facts"]


def test_positive_fallback_cannot_mask_model_failure_or_rewrite_received_author(
    demo, monkeypatch
):
    def fail(_):
        raise APIError("synthetic outage")

    demo.client.post("/patient", data={"set_author": "1", "caregiver": "1"})
    monkeypatch.setattr("web.app.MasterExtractor", lambda _, **kwargs: fail)
    html = post(demo, "dobrý").get_data(as_text=True)
    assert "synthetic outage" in html
    assert sessions[demo.key]["contact"] is None
    assert sessions[demo.key]["received_message"].author == "caregiver"
    html = demo.client.post("/patient", data={"set_author": "1"}).get_data(as_text=True)
    assert "Autora lze změnit jen před odesláním nové odpovědi" in html
    assert sessions[demo.key]["received_message"].author == "caregiver"
    assert not demo.path.exists()


def test_clarification_requires_actual_confirmed_answer(demo):
    from web.triage import assess_contact

    demo.answers["pocit"] = 1
    post(demo, "dobrý")
    post(demo, "2")
    packet = sessions[demo.key]["contact"].snapshot()
    assert not packet["question_answers"][0]["confirmed"]
    result = assess_contact(packet, demo.patient, demo.at)
    assert result["color"] == "yellow"
    assert not result["clarified_facts"]
    assert result["unprocessed_facts"]
