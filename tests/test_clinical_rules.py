"""Clinical rule boundaries, missing facts, provenance and form integration."""

import json
from copy import deepcopy

import pytest

from meddi.form import prepare_checkin
from meddi.loader import load_patient
from meddi.triage import evaluate_checkin
from tests.test_checkin_triage import neutral_forms, prepared, reason
from tests.test_form import answer, questionnaire


def evaluate(observations=None, context=None, vitals=None):
    data = prepared(*neutral_forms())
    data["vital_signs"].update(vitals or {})
    return evaluate_checkin(data, context, observations)


def skipped(result, rule_id):
    return next(item for item in result["skipped_rules"] if item["rule_id"] == rule_id)


@pytest.mark.parametrize(
    "observations,context,color",
    [
        ({}, {}, "green"),
        ({}, {"chemotherapy_within_6_weeks": True}, "green"),
        ({"chills": False}, {}, "green"),
        ({"chills": True}, {"chemotherapy_within_6_weeks": False}, "green"),
        ({"chills": True}, {}, "red"),
    ],
)
def test_missing_context_escalates_only_an_established_non_rejected_symptom(
    observations, context, color
):
    result = evaluate(observations, context)
    assert result["color"] == color
    if color == "red":
        why = reason(result, "chemotherapy_chills")
        assert why["provisional"]
        assert "§6.4" in why["uncertainty_source"]
        assert skipped(result, "chemotherapy_chills")["missing_fields"] == [
            "chemotherapy_within_6_weeks"
        ]


@pytest.mark.parametrize(
    "rule_id,color,observations,context",
    [
        (
            "grade_two_symptom",
            "yellow",
            {"grade_2_symptom_without_warning_signs": True},
            {},
        ),
        (
            "chemotherapy_chills",
            "red",
            {"chills": True},
            {"chemotherapy_within_6_weeks": True},
        ),
        ("rest_breathlessness", "red", {"breathlessness_at_rest": True}, {}),
        (
            "sudden_breathlessness_with_cardiac_symptoms",
            "red",
            {"sudden_breathlessness": True, "palpitations": True},
            {},
        ),
        ("reported_new_chest_pain", "red", {"new_chest_pain": True}, {}),
        ("diarrhea_severe_or_bloody", "red", {"stools_above_baseline_24h": 7}, {}),
        ("diarrhea_severe_or_bloody", "red", {"diarrhea_with_blood": True}, {}),
        ("orthopnea", "orange", {"orthopnea": True}, {}),
        (
            "oxygen_baseline_drop",
            "orange",
            {"spo2_pct": 94, "baseline_spo2_pct": 97},
            {},
        ),
        (
            "high_risk_treatment_diarrhea",
            "orange",
            {"stools_above_baseline_24h": 4},
            {"immunotherapy": True},
        ),
        (
            "high_risk_treatment_diarrhea",
            "orange",
            {"stools_above_baseline_24h": 6},
            {"fluoropyrimidine_treatment": True},
        ),
        (
            "high_risk_treatment_diarrhea",
            "orange",
            {"stools_above_baseline_24h": 5},
            {"irinotecan_treatment": True},
        ),
        (
            "loperamide_refractory_diarrhea",
            "orange",
            {
                "diarrhea": True,
                "loperamide_ineffective": True,
                "loperamide_scheme_followed": True,
            },
            {},
        ),
        (
            "immunotherapy_diarrhea_with_pain",
            "orange",
            {"diarrhea": True, "abdominal_pain": True},
            {"immunotherapy": True},
        ),
        (
            "unilateral_calf_swelling_and_pain",
            "orange",
            {"unilateral_calf_swelling": True, "calf_pain": True},
            {},
        ),
        ("hopelessness", "orange", {"hopelessness": True}, {}),
        (
            "worsening_despite_planned_examination",
            "orange",
            {"worsening_despite_planned_examination": True},
            {},
        ),
        ("constipation_three_days", "yellow", {"constipation_days": 3}, {}),
        (
            "paronychia_limits_activity",
            "yellow",
            {"paronychia_limits_activity": True},
            {},
        ),
        (
            "hand_foot_limits_activity",
            "yellow",
            {"hand_foot_limits_activity": True},
            {},
        ),
        (
            "mild_immunotherapy_diarrhea",
            "yellow",
            {"stools_above_baseline_24h": 3},
            {"immunotherapy": True},
        ),
        (
            "persistent_neuropathy",
            "yellow",
            {"neuropathy_persistent_between_cycles": True},
            {},
        ),
        (
            "persistent_neuropathy",
            "yellow",
            {"neuropathy_limits_fine_motor_skills": True},
            {},
        ),
        (
            "cisplatin_tinnitus",
            "yellow",
            {"new_tinnitus": True},
            {"cisplatin_treatment": True},
        ),
        (
            "cardiotoxic_edema_or_weight_gain",
            "yellow",
            {"edema_grade_2": True},
            {"cardiotoxic_treatment": True},
        ),
        (
            "cardiotoxic_edema_or_weight_gain",
            "yellow",
            {"weight_gain_3_days_kg": 2.1},
            {"cardiotoxic_treatment": True},
        ),
        ("monthly_weight_loss", "yellow", {"weight_loss_month_pct": 5}, {}),
        ("functional_status_decline", "yellow", {"functional_status_drop": 2}, {}),
        (
            "progressive_intake_decline",
            "yellow",
            {"progressive_intake_decline": True},
            {},
        ),
        ("moderate_psychological_distress", "yellow", {"moderate_sadness": True}, {}),
        ("moderate_psychological_distress", "yellow", {"moderate_anxiety": True}, {}),
        ("caregiver_exhaustion", "yellow", {"caregiver_exhaustion": True}, {}),
        ("medication_nonadherence", "yellow", {"medication_nonadherence": True}, {}),
        ("three_missed_checkins", "yellow", {"consecutive_missed_checkins": 3}, {}),
        ("unfavorable_trend", "yellow", {"unfavorable_trend": True}, {}),
        (
            "immunotherapy_new_symptom",
            "yellow",
            {"new_cough": True},
            {"immunotherapy": True},
        ),
        (
            "irinotecan_diarrhea_not_resolved",
            "yellow",
            {"hours_without_diarrhea": 11.9},
            {"irinotecan_treatment": True},
        ),
        (
            "reported_fever",
            "red",
            {"temperature_c": 38},
            {"chemotherapy_within_6_weeks": True},
        ),
        ("reported_oxygen_red", "red", {"spo2_pct": 89}, {}),
        ("reported_oxygen_orange", "orange", {"spo2_pct": 90}, {}),
        (
            "reported_suicidal_thoughts",
            "orange",
            {"suicidal_thoughts": True},
            {"suicide_plan_intent_or_means": False},
        ),
        (
            "suicidal_thoughts_with_plan",
            "red",
            {"suicidal_thoughts": True, "suicide_plan_intent_or_means": True},
            {},
        ),
    ],
)
def test_remaining_protocol_conditions_with_traceable_evidence(
    rule_id, color, observations, context
):
    result = evaluate(observations, context)
    assert result["color"] == color
    why = reason(result, rule_id)
    assert why["evidence"]
    assert "pravidla_triaze.md, §" in why["source"]
    assert not why["provisional"]


@pytest.mark.parametrize(
    "observations,context,rule_id",
    [
        ({"constipation_days": 2}, {}, "constipation_three_days"),
        (
            {"weight_gain_3_days_kg": 2, "edema_grade_2": False},
            {"cardiotoxic_treatment": True},
            "cardiotoxic_edema_or_weight_gain",
        ),
        ({"weight_loss_month_pct": 4.99}, {}, "monthly_weight_loss"),
        ({"functional_status_drop": 1}, {}, "functional_status_decline"),
        ({"consecutive_missed_checkins": 2}, {}, "three_missed_checkins"),
        ({"spo2_pct": 94, "baseline_spo2_pct": 96.9}, {}, "oxygen_baseline_drop"),
        (
            {"stools_above_baseline_24h": 3},
            {"fluoropyrimidine_treatment": True},
            "high_risk_treatment_diarrhea",
        ),
        (
            {"diarrhea": False, "hours_without_diarrhea": 12},
            {"irinotecan_treatment": True},
            "irinotecan_diarrhea_not_resolved",
        ),
        (
            {
                "diarrhea": True,
                "loperamide_ineffective": True,
                "loperamide_scheme_followed": False,
            },
            {},
            "loperamide_refractory_diarrhea",
        ),
    ],
)
def test_boundary_does_not_trigger_rule(observations, context, rule_id):
    result = evaluate(observations, context)
    assert not any(r["rule_id"] == rule_id for r in result["reasons"])


def test_loperamide_use_alone_does_not_prove_adherence_or_failure():
    result = evaluate({"diarrhea": True, "loperamide_ineffective": True})
    assert not any(
        r["rule_id"] == "loperamide_refractory_diarrhea" for r in result["reasons"]
    )
    assert skipped(result, "loperamide_refractory_diarrhea")["missing_fields"] == [
        "loperamide_scheme_followed"
    ]


def test_diarrhea_with_unknown_timing_keeps_provisional_irinotecan_rule():
    data = prepared(
        questionnaire(
            "nezadouci_ucinky", answer("prujem", "Do tří navíc za posledních 24 h", 0)
        )
    )
    result = evaluate_checkin(data, {"irinotecan_treatment": True})
    assert result["color"] == "yellow"
    assert reason(result, "irinotecan_diarrhea_not_resolved")["provisional"]
    assert (
        "hours_without_diarrhea"
        in skipped(result, "irinotecan_diarrhea_not_resolved")["missing_fields"]
    )


@pytest.mark.parametrize("hours", [12, 24])
def test_known_symptom_free_interval_does_not_activate_uncertain_timing(hours):
    result = evaluate(
        {"diarrhea": True, "hours_without_diarrhea": hours},
        {"irinotecan_treatment": True, "immunotherapy": False},
    )
    assert not any(
        item["rule_id"] == "irinotecan_diarrhea_not_resolved"
        for item in result["reasons"]
    )


def test_missing_diarrhea_timing_alone_does_not_escalate():
    result = evaluate({}, {"irinotecan_treatment": True})
    assert result["color"] == "green"
    assert not result["reasons"]


def test_neuropathy_question_does_not_prove_fine_motor_impairment():
    data = prepared(
        questionnaire(
            "nezadouci_ucinky", answer("brneni", "Střední omezení běžných činností", 1)
        )
    )
    result = evaluate_checkin(data)
    assert not any(r["rule_id"] == "persistent_neuropathy" for r in result["reasons"])
    assert skipped(result, "persistent_neuropathy")


@pytest.mark.parametrize(
    "index,color", [(0, "green"), (1, "yellow"), (2, "yellow"), (3, "yellow")]
)
def test_nausea_with_reduced_intake_is_a_yellow_minimum(index, color):
    data = prepared(
        questionnaire(
            "nezadouci_ucinky", answer("nevolnost", "Synthetic answer", index)
        )
    )
    result = evaluate_checkin(data)
    assert result["color"] == color
    if index:
        why = reason(result, "nausea_reduced_intake")
        assert why["evidence"][0]["question_id"] == "nevolnost"
        assert "§4" in why["source"]
    assert not any(
        item["code"] == "unassessed_answer" for item in result["review_issues"]
    )


def test_actual_c02_triggers_yellow_without_using_reference_data():
    patient = load_patient("ONC-001")
    checkin = next(c for c in patient["checkiny"] if c["checkin_id"] == "ONC-001-C02")
    result = evaluate_checkin(prepare_checkin(checkin))
    assert result["color"] == "yellow"
    assert reason(result, "nausea_reduced_intake")["evidence"][0]["option_indices"] == 1


@pytest.mark.parametrize(
    "systolic,diastolic,color",
    [
        (179.99, 109.99, "green"),
        (180, 80, "red"),
        (120, 110, "red"),
        (90, 70, "green"),
        (89.99, 70, "red"),
    ],
)
def test_pressure_thresholds_use_either_component(systolic, diastolic, color):
    result = evaluate(
        context={"antiangiogenic_treatment": False},
        vitals={
            "tk_sys": {"hodnota": systolic, "zdroj": "synthetic-cuff"},
            "tk_dia": {"hodnota": diastolic, "zdroj": "synthetic-cuff"},
        },
    )
    assert result["color"] == color
    if color == "red":
        why = reason(
            result, "systolic_hypotension" if systolic < 90 else "severe_hypertension"
        )
        assert why["evidence"][0]["kind"] == "vital_sign"
    assert not any(
        item["code"] == "unassessed_measurement" for item in result["review_issues"]
    )


def test_pressure_missing_component_does_not_block_proven_red():
    result = evaluate(observations={"systolic_bp": 180})
    assert result["color"] == "red"
    assert result["scores"]["severe_hypertension"] == 4
    result = evaluate(observations={"systolic_bp": 150})
    assert result["color"] == "green"
    assert skipped(result, "severe_hypertension")["missing_fields"] == ["diastolic_bp"]


@pytest.mark.parametrize(
    "systolic,diastolic,treatment,color",
    [
        (159.9, 99.9, True, "green"),
        (160, 80, True, "orange"),
        (120, 100, True, "orange"),
        (160, 80, False, "green"),
        (160, 80, None, "orange"),
    ],
)
def test_antiangiogenic_pressure_requires_treatment(
    systolic, diastolic, treatment, color
):
    result = evaluate(
        {"systolic_bp": systolic, "diastolic_bp": diastolic},
        {"antiangiogenic_treatment": treatment},
    )
    assert result["color"] == color
    if treatment is None:
        assert reason(result, "antiangiogenic_hypertension")["provisional"]
        assert skipped(result, "antiangiogenic_hypertension")["missing_fields"] == [
            "antiangiogenic_treatment"
        ]


@pytest.mark.parametrize("count,color", [(2, "green"), (3, "yellow")])
def test_repeated_elevated_pressure_requires_three_measurements(count, color):
    assert evaluate({"elevated_bp_measurements": count})["color"] == color


def test_hypertension_and_warning_symptom_escalate_together():
    result = evaluate({"high_blood_pressure": True, "vision_disturbance": True})
    assert result["color"] == "red"
    assert reason(result, "hypertension_with_warning_signs")
    assert (
        evaluate({"high_blood_pressure": False, "vision_disturbance": True})["color"]
        == "green"
    )
    missing = evaluate(
        {"systolic_bp": 140, "diastolic_bp": 85, "vision_disturbance": True}
    )
    assert not any(
        r["rule_id"] == "hypertension_with_warning_signs" for r in missing["reasons"]
    )
    assert skipped(missing, "hypertension_with_warning_signs")["missing_fields"] == [
        "high_blood_pressure"
    ]


@pytest.mark.parametrize(
    "field", ["blood_in_stool", "blood_in_vomit", "black_stool", "blood_in_urine"]
)
def test_each_critical_bleeding_site_is_independently_red(field):
    result = evaluate(
        {field: {"value": True, "source": "synthetic-confirmed-report"}},
        {"anticoagulation": False},
    )
    assert result["color"] == "red"
    assert (
        reason(result, "critical_bleeding")["evidence"][0]["source"]
        == "synthetic-confirmed-report"
    )


@pytest.mark.parametrize("minutes,color", [(0, "green"), (20, "green"), (20.1, "red")])
def test_nosebleed_strict_threshold(minutes, color):
    assert (
        evaluate({"nosebleed_minutes": minutes}, {"anticoagulation": False})["color"]
        == color
    )


@pytest.mark.parametrize(
    "injury,treatment,color",
    [(True, True, "red"), (True, None, "red"), (False, None, "green")],
)
def test_head_injury_requires_anticoagulation(injury, treatment, color):
    result = evaluate({"head_injury": injury}, {"anticoagulation": treatment})
    assert result["color"] == color
    if injury and treatment is None:
        assert reason(result, "head_injury_on_anticoagulation")["provisional"]
        assert skipped(result, "head_injury_on_anticoagulation")["missing_fields"] == [
            "anticoagulation"
        ]
    if not injury:
        assert not any(
            item["rule_id"] == "head_injury_on_anticoagulation"
            for item in result["skipped_rules"]
        )


def test_composite_bleeding_answer_does_not_invent_a_bleeding_site():
    data = prepared(questionnaire("nezadouci_ucinky", answer("krvaceni", "Ano", 1)))
    result = evaluate_checkin(data, {"anticoagulation": True})
    assert result["color"] == "orange"
    assert (
        reason(result, "bleeding_on_anticoagulation")["evidence"][0]["question_id"]
        == "krvaceni"
    )
    assert "blood_in_stool" in skipped(result, "critical_bleeding")["missing_fields"]
    unknown = evaluate_checkin(data)
    assert unknown["color"] == "orange"
    assert reason(unknown, "bleeding_on_anticoagulation")["provisional"]


def test_composite_urinary_answer_does_not_invent_blood_in_urine():
    data = prepared(questionnaire("nezadouci_ucinky", answer("moceni", "Ano", 1)))
    result = evaluate_checkin(data)
    assert result["color"] == "yellow"
    assert reason(result, "clinical_review_required")["provisional"]
    assert not any(item["rule_id"] == "critical_bleeding" for item in result["reasons"])


@pytest.mark.parametrize("hours,color", [(0, "green"), (10, "green"), (10.01, "red")])
def test_anuria_strict_threshold(hours, color):
    assert evaluate({"hours_without_urine": hours})["color"] == color


@pytest.mark.parametrize(
    "observations,color,rule_id",
    [
        ({"fainting": True}, "red", "fainting"),
        ({"cannot_keep_fluids": True}, "orange", "cannot_keep_fluids"),
        (
            {"cannot_keep_fluids": True, "dehydration_signs": True},
            "red",
            "fluid_intolerance_with_dehydration",
        ),
        (
            {"new_only_liquid_food": True, "pain_uncontrolled": True},
            "orange",
            "new_liquid_diet_with_uncontrolled_pain",
        ),
        (
            {"reduced_intake": True, "orthostatic_dizziness": True},
            "orange",
            "reduced_intake_with_circulatory_signs",
        ),
        (
            {"hypotension": True, "orthostatic_dizziness": True},
            "yellow",
            "orthostatic_hypotension",
        ),
        (
            {"vomiting_episodes_24h": 3, "drinking_maintained": True},
            "yellow",
            "vomiting_with_preserved_drinking",
        ),
        (
            {"vomiting_episodes_24h": 5, "cannot_keep_fluids": True},
            "orange",
            "vomiting_with_fluid_intolerance",
        ),
        (
            {"no_gas": True, "no_stool": True, "vomiting": True},
            "red",
            "bowel_obstruction_signs",
        ),
    ],
)
def test_fluid_circulation_and_intake_combinations(observations, color, rule_id):
    result = evaluate(observations)
    assert result["color"] == color
    assert reason(result, rule_id)["source"]


def test_vomiting_range_is_not_replaced_by_a_fictitious_count():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("zvraceni", "3–5 epizod", 1))
    )
    result = evaluate_checkin(data, observations={"drinking_maintained": True})
    assert result["color"] == "yellow"
    assert any(
        item.get("question_id") == "zvraceni"
        for item in reason(result, "vomiting_with_preserved_drinking")["evidence"]
    )


@pytest.mark.parametrize("count,color", [(0, "green"), (5, "green"), (6, "red")])
def test_explicit_vomiting_count_and_zero_are_evaluated(count, color):
    result = evaluate({"vomiting_episodes_24h": count})
    assert result["color"] == color
    assert not any(item["rule_id"] == "vomiting" for item in result["skipped_rules"])


def test_range_rejects_unmet_condition_without_requesting_an_exact_count():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("zvraceni", "1–2 epizody", 0))
    )
    result = evaluate_checkin(data)
    assert not any(
        item["rule_id"]
        in (
            "vomiting",
            "vomiting_with_preserved_drinking",
            "vomiting_with_fluid_intolerance",
        )
        for item in result["skipped_rules"]
    )


@pytest.mark.parametrize(
    "field",
    [
        "confusion",
        "consciousness_disturbance",
        "difficulty_waking",
        "seizure",
        "new_limb_weakness",
        "speech_disturbance",
        "unresponsiveness",
    ],
)
def test_each_neurological_red_flag_is_sufficient(field):
    result = evaluate({field: True})
    assert result["color"] == "red"
    assert reason(result, "neurological_red_flags")["evidence"][0]["field"] == field


def test_brain_tumor_rule_needs_morning_headache_and_vomiting():
    result = evaluate(
        {"morning_headache": True, "vomiting": True}, {"brain_tumor": True}
    )
    assert result["color"] == "orange"
    assert reason(result, "brain_tumor_morning_headache")
    assert (
        evaluate({"morning_headache": False, "vomiting": True}, {"brain_tumor": True})[
            "color"
        ]
        == "green"
    )


@pytest.mark.parametrize("treatment", ["diabetes", "immunotherapy"])
def test_metabolic_red_flags_require_all_symptoms_and_risk_context(treatment):
    observations = {"vomiting": True, "abdominal_pain": True, "rapid_breathing": True}
    result = evaluate(observations, {treatment: True})
    assert result["color"] == "red"
    assert reason(result, "metabolic_red_flags")
    del observations["rapid_breathing"]
    result = evaluate(observations, {treatment: True})
    assert result["color"] == "green"
    assert skipped(result, "metabolic_red_flags")["missing_fields"] == [
        "rapid_breathing"
    ]
    observations["rapid_breathing"] = False
    result = evaluate(observations, {treatment: True})
    assert not any(
        item["rule_id"] == "metabolic_red_flags" for item in result["skipped_rules"]
    )


@pytest.mark.parametrize(
    "glucose,insulin,color",
    [
        (3.99, True, "orange"),
        (4, True, "green"),
        (3, False, "green"),
        (3, None, "orange"),
    ],
)
def test_low_glucose_boundary_and_insulin_context(glucose, insulin, color):
    result = evaluate(
        context={"insulin_treatment": insulin},
        vitals={
            "glykemie_mmol_l": {"hodnota": glucose, "zdroj": "synthetic-glucometer"}
        },
    )
    assert result["color"] == color
    if insulin is None:
        assert reason(result, "hypoglycemia_on_insulin")["provisional"]
        assert skipped(result, "hypoglycemia_on_insulin")["missing_fields"] == [
            "insulin_treatment"
        ]


@pytest.mark.parametrize("glucose,color", [(15, "green"), (15.01, "yellow")])
def test_symptomatic_hyperglycemia_strict_boundary(glucose, color):
    assert (
        evaluate(
            {"glucose_mmol_l": glucose, "polydipsia": True, "frequent_urination": True}
        )["color"]
        == color
    )


def test_immunotherapy_metabolic_symptoms_require_weight_loss_too():
    observations = {"polydipsia": True, "frequent_urination": True, "weight_loss": True}
    assert evaluate(observations, {"immunotherapy": True})["color"] == "orange"
    del observations["weight_loss"]
    result = evaluate(observations, {"immunotherapy": True})
    assert result["color"] == "green"
    assert skipped(result, "immunotherapy_metabolic_symptoms")["missing_fields"] == [
        "weight_loss"
    ]


@pytest.mark.parametrize(
    "field", ["new_marked_drowsiness", "unresponsiveness", "slow_breathing"]
)
def test_opioid_rule_uses_explicit_symptoms_and_treatment(field):
    result = evaluate({field: True}, {"opioid_treatment": True})
    assert result["color"] == "red"
    assert reason(result, "opioid_red_flags")
    result = evaluate({field: True})
    assert skipped(result, "opioid_red_flags")["missing_fields"] == ["opioid_treatment"]
    assert result["color"] == "red"
    assert reason(result, "opioid_red_flags")["provisional"]


def test_nausea_does_not_lower_proven_red_and_keeps_all_reasons():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("nevolnost", "Omezený příjem", 1))
    )
    result = evaluate_checkin(data, observations={"confusion": True})
    assert result["color"] == "red"
    assert {item["rule_id"] for item in result["reasons"]} == {
        "nausea_reduced_intake",
        "neurological_red_flags",
    }


def test_derived_and_supplied_fact_conflict_is_visible_and_keeps_worse_value():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("nevolnost", "Bez omezení", 0))
    )
    result = evaluate_checkin(data, observations={"nausea_reduced_intake": True})
    assert result["color"] == "yellow"
    assert any(
        item["code"] == "conflicting_observation" for item in result["review_issues"]
    )


@pytest.mark.parametrize(
    "observations,context",
    [
        ({"confusion": "false"}, {}),
        ({"systolic_bp": True}, {}),
        ({"hours_without_urine": float("nan")}, {}),
        ({"glucose_mmol_l": -1}, {}),
        ({}, {"anticoagulation": "yes"}),
    ],
)
def test_invalid_values_are_not_silently_used_as_facts(observations, context):
    with pytest.raises(ValueError):
        evaluate(observations, context)


def test_provenance_is_json_ready_and_does_not_share_input_data():
    observations = {
        "confusion": {
            "value": True,
            "source": {"field": "patient_message", "quote": "Synthetic report"},
        }
    }
    before = deepcopy(observations)
    result = evaluate(observations)
    json.dumps(result, ensure_ascii=False)
    reason(result, "neurological_red_flags")["evidence"][0]["source"]["quote"] = (
        "changed"
    )
    assert observations == before


def test_cli_accepts_explicit_observations(tmp_path, monkeypatch, capsys):
    from meddi.triage import main

    input_file, observations_file = (
        tmp_path / "prepared.json",
        tmp_path / "observations.json",
    )
    input_file.write_text(json.dumps(prepared(*neutral_forms())), encoding="utf-8")
    observations_file.write_text(json.dumps({"confusion": True}), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "triage",
            str(input_file),
            "--checkin",
            "--observations",
            str(observations_file),
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["color"] == "red"
