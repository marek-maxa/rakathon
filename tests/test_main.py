"""Compare actual rule results with separate, ID-paired references."""

import io
from copy import deepcopy
from datetime import date, timedelta

import pytest

import main as app
from meddi.patient_inputs import build_triage_inputs
from tests.test_form import answer, checkin, questionnaire


def patient_with_checkins():
    first = checkin(questionnaire("bolest_analgeticka_terapie", answer("nrs", 5)))
    first["checkin_id"] = "synthetic-C01"
    first["vitalni_funkce"]["teplota_c"]["hodnota"] = 36.8
    second = deepcopy(first)
    second["checkin_id"] = "synthetic-C02"
    second["dotazniky"] = []
    second["vitalni_funkce"] = None
    return {
        "patient_id": "synthetic",
        "checkiny": [first, second],
        "nazev_scenare": "not an input",
    }


def references():
    # Intentionally reversed; references must be matched by ID, not position.
    return [
        {"checkin_id": "synthetic-C02", "uroven": 1, "zduvodneni": "Reference second"},
        {"checkin_id": "synthetic-C01", "uroven": 2, "zduvodneni": "Reference first"},
    ]


def treatment_patient():
    patient = patient_with_checkins()
    patient["checkiny"] = patient["checkiny"][:1]
    patient["checkiny"][0]["zprava_pacienta"] = None
    patient["lecba"] = {
        "leky": ["5-FU 400 mg D1"],
        "cykly": [{"datum_d1": "2026-10-15", "cyklus": 1}],
    }
    patient["leky"] = []
    return patient


def test_time_adapter_excludes_future_data_scenarios_notes_and_doses():
    patient = treatment_patient()
    current = patient["checkiny"][0]
    before = build_triage_inputs(patient, current)
    future = deepcopy(current)
    future.update(
        checkin_id="future",
        datum="2026-10-17",
        vitalni_funkce={"tk_sys": {"hodnota": 200}},
    )
    patient["checkiny"].append(future)
    patient["lecba"]["cykly"].append({"datum_d1": "2026-10-17", "cyklus": 2})
    patient["lecba"]["poznamka"] = "Future chemotherapy stopped"
    patient["lecba"]["rezim"] = "Future nivolumab"
    patient["nazev_scenare"] = "Future dangerous result"
    patient["leky"].append({"lek": "Warfarin", "od_data": "2026-10-17"})
    patient["laboratore"] = [{"datum": "2026-10-17", "hodnota": 999}]
    patient["udalosti_tymu"] = [{"datum": "2026-10-17", "text": "hospitalization"}]
    assert build_triage_inputs(patient, current) == before


def test_messages_and_free_text_do_not_create_clinical_observations():
    patient = treatment_patient()
    current = patient["checkiny"][0]
    _, context, observations = build_triage_inputs(patient, current)
    current["zprava_pacienta"] = "Nemocim 24 hodin, jsem zmateny a mam zimnici."
    current["dotazniky"].append(
        questionnaire("nezadouci_ucinky", answer("jine", "neudrzim tekutiny"))
    )
    prepared, after_context, after_observations = build_triage_inputs(patient, current)
    assert after_observations == observations
    assert after_context == context
    result = app.evaluate_checkin(prepared, context=context, observations=observations)
    assert result["color"] == "yellow"  # Existing structured NRS 5, not the text.
    assert any(
        i["code"] == "unassessed_patient_message" for i in result["review_issues"]
    )


@pytest.mark.parametrize("elapsed,expected", [(0, True), (42, True), (43, None)])
def test_recent_chemotherapy_requires_known_drug_and_dated_administration(
    elapsed, expected
):
    patient = treatment_patient()
    current = patient["checkiny"][0]
    patient["lecba"]["cykly"][0]["datum_d1"] = (
        date.fromisoformat(current["datum"]) - timedelta(days=elapsed)
    ).isoformat()
    _, context, _ = build_triage_inputs(patient, current)
    assert context["chemotherapy_within_6_weeks"] is expected
    patient["lecba"]["leky"] = ["unknown compound"]
    _, context, _ = build_triage_inputs(patient, current)
    assert context["chemotherapy_within_6_weeks"] is None


def test_cycle_alone_does_not_classify_immunotherapy_as_chemotherapy():
    patient = treatment_patient()
    patient["lecba"]["leky"] = ["nivolumab"]
    _, context, _ = build_triage_inputs(patient, patient["checkiny"][0])
    assert context["immunotherapy"] is True
    assert context["chemotherapy_within_6_weeks"] is None


def test_context_evidence_cannot_mutate_patient_history():
    patient = treatment_patient()
    original = deepcopy(patient)
    prepared, _, _ = build_triage_inputs(patient, patient["checkiny"][0])
    prepared["context_sources"]["chemotherapy_within_6_weeks"]["cycles"][0][
        "datum_d1"
    ] = "1900-01-01"
    assert patient == original


@pytest.mark.parametrize(
    "start,expected", [("2026-10-15", True), ("2026-10-16", None), ("2026-10-17", None)]
)
def test_medication_start_date_is_respected_without_guessing_same_day_time(
    start, expected
):
    patient = treatment_patient()
    patient["leky"] = [
        {"lek": "Warfarin", "od_data": start, "davka": "Future new dose on D20"}
    ]
    _, context, _ = build_triage_inputs(patient, patient["checkiny"][0])
    assert context["anticoagulation"] is expected


def test_three_missed_forms_count_history_and_reset_after_completion():
    patient = treatment_patient()
    first = deepcopy(patient["checkiny"][0])
    for offset in range(1, 4):
        item = deepcopy(first)
        item.update(
            checkin_id=f"missing-{offset}",
            datum=f"2026-10-{16 + offset}",
            stav="nevyplneno",
            dotazniky=[],
            vitalni_funkce=None,
        )
        patient["checkiny"].append(item)
        prepared, context, observations = build_triage_inputs(patient, item)
        result = app.evaluate_checkin(prepared, context, observations)
        assert observations["consecutive_missed_checkins"]["value"] == offset
        assert result["color"] == ("yellow" if offset == 3 else "green")
    resumed = deepcopy(first)
    resumed.update(checkin_id="resumed", datum="2026-10-20")
    patient["checkiny"].append(resumed)
    assert "consecutive_missed_checkins" not in build_triage_inputs(patient, resumed)[2]


def test_folfox_grade_two_diarrhea_uses_treatment_not_reference_or_text():
    from meddi.loader import load_patient

    patient = load_patient("ONC-002")
    current = next(c for c in patient["checkiny"] if c["checkin_id"] == "ONC-002-C08")
    current["zprava_pacienta"] = None
    prepared, context, observations = build_triage_inputs(patient, current)
    result = app.evaluate_checkin(prepared, context, observations)
    assert result["color"] == "orange"
    reason = next(
        r for r in result["reasons"] if r["rule_id"] == "high_risk_treatment_diarrhea"
    )
    assert any(
        e["kind"] == "context" and e["source"]["drugs"] for e in reason["evidence"]
    )


def test_history_measurements_use_only_past_values_and_preserve_sources():
    patient = treatment_patient()
    first = patient["checkiny"][0]
    first["vitalni_funkce"] = {"tk_sys": {"hodnota": 145}, "vaha_kg": {"hodnota": 70}}
    for day, weight in [(17, 71), (18, 72.1)]:
        item = deepcopy(first)
        item.update(checkin_id=f"day-{day}", datum=f"2026-10-{day}")
        item["vitalni_funkce"]["vaha_kg"]["hodnota"] = weight
        patient["checkiny"].append(item)
    _, _, observations = build_triage_inputs(patient, patient["checkiny"][-1])
    assert observations["elevated_bp_measurements"]["value"] == 3
    assert observations["weight_gain_3_days_kg"]["value"] == pytest.approx(2.1)
    assert (
        observations["weight_gain_3_days_kg"]["source"]["baseline_checkin"]
        == first["checkin_id"]
    )


def test_monthly_weight_loss_uses_recent_measurements_after_initial_month():
    patient = treatment_patient()
    first = patient["checkiny"][0]
    first["vitalni_funkce"] = {"vaha_kg": {"hodnota": 100}}
    current = deepcopy(first)
    current.update(checkin_id="month-later", datum="2026-11-16")
    current["vitalni_funkce"]["vaha_kg"]["hodnota"] = 95
    patient["checkiny"].append(current)
    _, _, observations = build_triage_inputs(patient, current)
    assert observations["weight_loss_month_pct"]["value"] == 5
    assert (
        observations["weight_loss_month_pct"]["source"]["checkin_id"]
        == first["checkin_id"]
    )


def test_missing_current_time_does_not_expose_same_day_history():
    patient = treatment_patient()
    first = patient["checkiny"][0]
    first["vitalni_funkce"] = {"tk_sys": {"hodnota": 180}}
    current = deepcopy(first)
    current.update(checkin_id="no-time", cas=None, vitalni_funkce=None)
    patient["checkiny"].append(current)
    assert "elevated_bp_measurements" not in build_triage_inputs(patient, current)[2]


def test_cli_lower_filter_still_reports_the_full_summary(monkeypatch, capsys):
    monkeypatch.setattr(app, "load_patient", lambda patient_id: patient_with_checkins())
    refs = references()
    refs[1]["uroven"] = 3
    monkeypatch.setattr(app, "load_ground_truth", lambda patient_id: refs)
    monkeypatch.setattr("sys.argv", ["main.py", "synthetic", "--comparison", "lower"])
    app.main()
    output = capsys.readouterr().out
    assert "synthetic-C01" in output
    assert "synthetic-C02" not in output
    assert "Lower: 1" in output
    assert "Matches: 0/2" in output


def test_compares_rule_results_by_id_and_preserves_undetermined():
    result = app.compare_patient(patient_with_checkins(), references())
    assert result[0]["rules_color"] == "yellow"
    assert result[0]["reference_color"] == "yellow"
    assert result[0]["comparison"] == "match"
    assert result[0]["reference_reason"] == "Reference first"
    assert result[1]["rules_color"] is None
    assert result[1]["reference_color"] == "green"
    assert result[1]["comparison"] == "undetermined"
    assert app.count_matches([{"checkins": result}]) == (1, 2)


@pytest.mark.parametrize(
    "level,comparison", [(1, "higher"), (2, "match"), (3, "lower"), (4, "lower")]
)
def test_relative_severity_comparison(level, comparison):
    refs = references()
    refs[1]["uroven"] = level
    result = app.compare_patient(patient_with_checkins(), refs)
    assert result[0]["comparison"] == comparison


def test_changing_references_does_not_change_rule_results(monkeypatch):
    patient = patient_with_checkins()
    seen_inputs = []
    evaluate = app.evaluate_checkin

    def capture(prepared, **kwargs):
        seen_inputs.append(deepcopy({"prepared": prepared, **kwargs}))
        return evaluate(prepared, **kwargs)

    monkeypatch.setattr(app, "evaluate_checkin", capture)
    first = app.compare_patient(patient, references())
    altered = references()
    for reference in altered:
        reference.update(uroven=4, zduvodneni="Different evaluation")
    second = app.compare_patient(patient, altered)
    assert seen_inputs[:2] == seen_inputs[2:]
    assert all("nazev_scenare" not in prepared["prepared"] for prepared in seen_inputs)
    assert [row["rules_color"] for row in first] == [
        row["rules_color"] for row in second
    ]
    assert [row["reasons"] for row in first] == [row["reasons"] for row in second]


@pytest.mark.parametrize(
    "problem", ["duplicate_checkin", "duplicate_reference", "missing_reference"]
)
def test_rejects_ambiguous_or_missing_reference_pairs(problem):
    patient = patient_with_checkins()
    refs = references()
    if problem == "duplicate_checkin":
        patient["checkiny"].append(deepcopy(patient["checkiny"][0]))
    elif problem == "duplicate_reference":
        refs.append(deepcopy(refs[0]))
    else:
        refs.pop()
    with pytest.raises(ValueError):
        app.compare_patient(patient, refs)


def test_missing_rescue_response_does_not_create_an_escalation_or_hide_red():
    patient = patient_with_checkins()
    patient["checkiny"][0]["dotazniky"] = [
        questionnaire("bolest_analgeticka_terapie", answer("nrs", 7)),
        questionnaire("nezadouci_ucinky", answer("bol_hrud", "Nová bolest", 1)),
    ]
    result = app.compare_patient(patient, references())
    assert result[0]["rules_color"] == "red"
    assert not result[0]["provisional"]
    assert any(
        item["missing_fields"] == ["pain_persists_after_rescue_dose"]
        for item in result[0]["skipped_rules"]
    )
    patient["checkiny"][0]["dotazniky"].pop()
    result = app.compare_patient(patient, references())
    assert result[0]["rules_color"] == "green"
    assert not result[0]["provisional"]


@pytest.mark.parametrize("details", [False, True])
def test_cli_prints_every_checkin_and_optional_reasons(monkeypatch, capsys, details):
    monkeypatch.setattr(app, "list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr(app, "load_patient", lambda patient_id: patient_with_checkins())
    monkeypatch.setattr(app, "load_ground_truth", lambda patient_id: references())
    monkeypatch.setattr("sys.argv", ["main.py", *(["--details"] if details else [])])
    app.main()
    output = capsys.readouterr().out
    assert "GROUND TRUTH" in output
    assert "RULES" in output
    assert output.count("synthetic-C01") == 1
    assert output.count("synthetic-C02") == 1
    assert "undetermined" in output
    assert "Matches: 1/2; undetermined: 1; review: 2" in output
    assert ("Reference first" in output) is details
    assert ("Bolest NRS je mezi 4 a 6." in output) is details
    assert ("Skipped [oxygen]: missing spo2_pct" in output) is details


def test_cli_patient_filter(monkeypatch, capsys):
    requested = []
    monkeypatch.setattr(
        app,
        "load_patient",
        lambda patient_id: requested.append(patient_id) or patient_with_checkins(),
    )
    monkeypatch.setattr(app, "load_ground_truth", lambda patient_id: references())
    monkeypatch.setattr("sys.argv", ["main.py", "synthetic"])
    app.main()
    assert requested == ["synthetic"]
    assert "synthetic-C01" in capsys.readouterr().out


def test_cli_details_handles_unicode_in_windows_output(monkeypatch):
    refs = references()
    refs[1]["zduvodneni"] = "Příznak ≥ 3 dny."
    monkeypatch.setattr(app, "load_patient", lambda patient_id: patient_with_checkins())
    monkeypatch.setattr(app, "load_ground_truth", lambda patient_id: refs)
    monkeypatch.setattr("sys.argv", ["main.py", "synthetic", "--details"])
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1250")
    monkeypatch.setattr("sys.stdout", stream)
    app.main()
    stream.flush()
    assert "Příznak ≥ 3 dny." in buffer.getvalue().decode("utf-8")
