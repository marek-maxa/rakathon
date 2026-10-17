"""Rule thresholds and evidence through the complete form -> triage path."""

import json
from copy import deepcopy

import pytest

from meddi.form import prepare_checkin
from meddi.triage import evaluate_checkin, evaluate_triage
from tests.test_form import answer, checkin, questionnaire


def prepared(*forms, temperature=36.8, oxygen=97):
    source = checkin(*forms)
    source["zprava_pacienta"] = None
    source["prilohy"] = []
    source["vitalni_funkce"] = {
        "teplota_c": {"hodnota": temperature, "zdroj": "synthetic-thermometer"},
        "spo2_pct": {"hodnota": oxygen, "zdroj": "synthetic-oximeter"},
    }
    return prepare_checkin(source)


def neutral_forms():
    return [
        questionnaire("nezadouci_ucinky", answer("pocit", "1", 0)),
        questionnaire("bolest_analgeticka_terapie", answer("nrs", 2)),
    ]


def reason(result, rule_id):
    return next(item for item in result["reasons"] if item["rule_id"] == rule_id)


@pytest.mark.parametrize(
    "temperature,chemotherapy,color,provisional",
    [
        (37.99, True, "green", False),
        (38, True, "red", False),
        (38.1, None, "red", True),
        (38.1, False, "yellow", False),
    ],
)
def test_fever_threshold_and_explicit_treatment_context(
    temperature, chemotherapy, color, provisional
):
    data = prepared(*neutral_forms(), temperature=temperature)
    context = {"chemotherapy_within_6_weeks": chemotherapy}
    before = deepcopy((data, context))
    result = evaluate_checkin(data, context)
    assert result["color"] == color
    assert (data, context) == before
    if color == "red":
        why = reason(result, "fever")
        assert why["provisional"] is provisional
        assert why["evidence"][0]["hodnota"] == temperature
        assert why["evidence"][1]["value"] is chemotherapy
        assert "Horečka" in why["source"]
        assert (
            any(item["rule_id"] == "fever" for item in result["skipped_rules"])
            is provisional
        )
        if provisional:
            assert "§6.4" in why["uncertainty_source"]
    elif color == "green":
        assert result["reasons"] == []
        assert result["requires_review"]  # Other newly supported rules lack inputs.
        if chemotherapy is None:
            skipped = next(
                item for item in result["skipped_rules"] if item["rule_id"] == "fever"
            )
            assert skipped["missing_fields"] == ["chemotherapy_within_6_weeks"]
    else:
        assert result["requires_review"] is True


@pytest.mark.parametrize(
    "oxygen,color", [(89.99, "red"), (90, "orange"), (91.99, "orange"), (92, "green")]
)
def test_oxygen_thresholds(oxygen, color):
    result = evaluate_checkin(prepared(*neutral_forms(), oxygen=oxygen))
    assert result["color"] == color
    if color != "green":
        assert reason(result, "oxygen")["evidence"][0]["zdroj"] == "synthetic-oximeter"


@pytest.mark.parametrize(
    "form,question,value,index,color,rule",
    [
        ("nezadouci_ucinky", "pocit", "5", 4, "orange", "overall_feeling"),
        (
            "nezadouci_ucinky",
            "dusnost",
            "Dušnost v klidu",
            3,
            "red",
            "breathlessness_at_rest",
        ),
        ("nezadouci_ucinky", "bol_hrud", "Nová bolest", 1, "red", "new_chest_pain"),
        ("nezadouci_ucinky", "zvraceni", "Více než 5", 2, "red", "vomiting"),
        (
            "nezadouci_ucinky",
            "prujem",
            "Více než 7",
            2,
            "red",
            "diarrhea_severe_or_bloody",
        ),
        ("bolest_analgeticka_terapie", "nrs", 4, None, "yellow", "pain"),
        ("bolest_analgeticka_terapie", "nrs", 6, None, "yellow", "pain"),
        ("bolest_analgeticka_terapie", "sos", 3, None, "yellow", "rescue_dose_count"),
    ],
)
def test_structured_answers_trigger_source_linked_reasons(
    form, question, value, index, color, rule
):
    data = prepared(questionnaire(form, answer(question, value, index)))
    result = evaluate_checkin(data)
    assert result["color"] == color
    why = reason(result, rule)
    assert why["evidence"][0]["question_id"] == question
    assert why["evidence"][0]["questionnaire_id"] == form
    assert why["evidence"][0]["value"] == value
    assert why["message"]
    assert "pravidla_triaze.md" in why["source"]
    assert result["non_green_answers"] == data["non_green_answers"]
    assert json.loads(json.dumps(result, ensure_ascii=False)) == result


@pytest.mark.parametrize(
    "persists,color,provisional",
    [
        (True, "orange", False),
        (None, "orange", True),
        (False, "yellow", False),
    ],
)
def test_severe_pain_does_not_infer_rescue_dose_effect(persists, color, provisional):
    data = prepared(
        questionnaire("bolest_analgeticka_terapie", answer("nrs", 7), answer("sos", 2))
    )
    result = evaluate_checkin(data, {"pain_persists_after_rescue_dose": persists})
    assert result["color"] == color
    if color == "orange":
        why = reason(result, "pain")
        assert why["provisional"] is provisional
        assert why["evidence"][-1]["value"] is persists
        if provisional:
            assert "§6.4" in why["uncertainty_source"]
    else:
        assert not any(item["rule_id"] == "pain" for item in result["reasons"])
        if persists is None:
            skipped = next(
                item for item in result["skipped_rules"] if item["rule_id"] == "pain"
            )
            assert skipped["missing_fields"] == ["pain_persists_after_rescue_dose"]
    assert result["requires_review"]  # Overall feeling has not been supplied.


@pytest.mark.parametrize(
    "details,color,provisional",
    [
        (True, "red", False),
        (False, "orange", False),
        (None, "red", True),
    ],
)
def test_uncolored_suicidal_thoughts_are_not_ignored(details, color, provisional):
    data = prepared(
        questionnaire("psychoonkologicky_screening", answer("sebevrazda", "Ano", 0))
    )
    assert data["non_green_answers"] == []
    result = evaluate_checkin(data, {"suicide_plan_intent_or_means": details})
    assert result["color"] == color
    assert reason(result, "suicidal_thoughts")["provisional"] is provisional
    if details is None:
        assert any(
            item["missing_fields"] == ["suicide_plan_intent_or_means"]
            for item in result["skipped_rules"]
        )


def test_temperature_range_is_evidence_not_an_invented_exact_temperature():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("teplota", "38–39 °C", 1)),
        temperature=None,
    )
    result = evaluate_checkin(data, {"chemotherapy_within_6_weeks": True})
    assert result["color"] == "red"
    why = reason(result, "fever")
    assert why["evidence"][0]["value"] == "38–39 °C"
    assert "hodnota" not in why["evidence"][0]


def test_conflicting_temperature_keeps_higher_level_and_requests_review():
    data = prepared(
        *neutral_forms(),
        questionnaire("nezadouci_ucinky", answer("teplota", "38–39", 1)),
    )
    result = evaluate_checkin(data, {"chemotherapy_within_6_weeks": True})
    assert result["color"] == "red"
    assert result["requires_review"]
    conflict = next(
        item
        for item in result["review_issues"]
        if item["code"] == "conflicting_temperature"
    )
    assert len(conflict["evidence"]) == 2


def test_highest_rule_wins_but_all_escalation_reasons_are_preserved():
    data = prepared(
        questionnaire(
            "nezadouci_ucinky",
            answer("pocit", "5", 4),
            answer("bol_hrud", "Nová bolest", 1),
        ),
        questionnaire("bolest_analgeticka_terapie", answer("nrs", 5)),
    )
    result = evaluate_checkin(data)
    assert result["color"] == "red"
    assert {item["rule_id"] for item in result["reasons"]} == {
        "overall_feeling",
        "new_chest_pain",
        "pain",
    }


def test_unassessed_esas_signal_sets_only_a_provisional_level():
    data = prepared(*neutral_forms(), questionnaire("esas", answer("bolest", 6)))
    assert data["non_green_answers"][0]["color"] == "red"
    result = evaluate_checkin(data)
    assert result["color"] == "red"
    why = reason(result, "unassessed_answer:esas:bolest")
    assert why["provisional"]
    assert "§6.4" in why["uncertainty_source"]
    assert "dotazniky_definice.json" in why["source"]
    assert why["evidence"][0]["value"] == 6
    assert result["scores"]["pain"] == 1  # ESAS was not converted to NRS.
    assert result["requires_review"]
    assert result["non_green_answers"] == data["non_green_answers"]


@pytest.mark.parametrize(
    "value,color",
    [
        (1, "yellow"),
        (3, "yellow"),
        (4, "yellow"),
        (5, "yellow"),
        (6, "red"),
        (10, "red"),
    ],
)
def test_unassessed_esas_preserves_definition_boundaries(value, color):
    data = prepared(*neutral_forms(), questionnaire("esas", answer("unava", value)))
    before = deepcopy(data)
    result = evaluate_checkin(data)
    assert result["color"] == color
    assert data == before
    if value >= 4:
        assert reason(result, "unassessed_answer:esas:unava")["provisional"]
        assert result["requires_review"]
    else:
        assert reason(result, "clinical_review_required")["provisional"]


@pytest.mark.parametrize(
    "data,color,rule",
    [
        (
            {"temperature_c": 38, "spo2_pct": 97, "pain_nrs": 1, "overall_feeling": 1},
            "red",
            "fever",
        ),
        (
            {"temperature_c": 36, "spo2_pct": 97, "pain_nrs": 8, "overall_feeling": 1},
            "orange",
            "pain",
        ),
    ],
)
def test_flat_provisional_level_still_requires_review_when_all_measurements_present(
    data, color, rule
):
    result = evaluate_triage(data)
    assert result["color"] == color
    assert result["requires_review"]
    assert any(item["rule_id"] == rule for item in result["skipped_rules"])


def test_uninterpreted_patient_message_is_retained_without_suppressing_color():
    data = prepared(*neutral_forms())
    data["patient_message"] = "V dotazníku jsem se spletl, nemůžu pít."
    result = evaluate_checkin(data)
    assert result["color"] == "yellow"
    assert result["doporuceny_krok"] == "kontaktovat_tym"
    assert result["requires_review"]
    issue = next(
        item
        for item in result["review_issues"]
        if item["code"] == "unassessed_patient_message"
    )
    assert issue["evidence"][0]["value"] == data["patient_message"]


def test_missing_checkin_without_known_stability_requires_human_review():
    data = prepare_checkin({"dotazniky": [], "stav": "nevyplneno"})
    result = evaluate_checkin(data)
    assert result["color"] == "yellow"
    assert result["minimum_color"] is None
    assert result["requires_review"]
    assert reason(result, "clinical_review_required")
    assert {item["rule_id"] for item in result["skipped_rules"]} >= {
        "fever",
        "oxygen",
        "overall_feeling",
        "pain",
    }


def test_missing_measurements_and_pain_are_skipped_without_blocking_known_green():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("pocit", "1", 0)),
        temperature=None,
        oxygen=None,
    )
    result = evaluate_checkin(data)
    assert result["color"] == "green"
    assert result["requires_review"]
    missing = {
        item["rule_id"]: item["missing_fields"]
        for item in result["skipped_rules"]
        if item["rule_id"] in ("fever", "oxygen", "pain")
    }
    assert missing == {
        "fever": ["temperature_c"],
        "oxygen": ["spo2_pct"],
        "pain": ["pain_nrs"],
    }
    assert result["scores"]["oxygen"] is None  # A skipped rule was not evaluated green.


def test_known_fever_retains_provisional_red_with_unknown_chemotherapy():
    data = prepared(temperature=38.2, oxygen=None)
    result = evaluate_checkin(data)
    assert result["color"] == "red"
    assert reason(result, "fever")["provisional"]
    assert next(item for item in result["skipped_rules"] if item["rule_id"] == "fever")[
        "missing_fields"
    ] == ["chemotherapy_within_6_weeks"]


def test_unknown_rescue_effect_does_not_hide_confirmed_yellow_dose_count():
    data = prepared(
        questionnaire("bolest_analgeticka_terapie", answer("nrs", 8), answer("sos", 3))
    )
    result = evaluate_checkin(data)
    assert result["color"] == "orange"
    assert {item["rule_id"] for item in result["reasons"]} == {
        "rescue_dose_count",
        "pain",
    }
    assert reason(result, "pain")["provisional"]
    assert any(
        item["missing_fields"] == ["pain_persists_after_rescue_dose"]
        for item in result["skipped_rules"]
    )


def test_flat_facts_skip_missing_criteria_and_preserve_their_names():
    result = evaluate_triage({"overall_feeling": 1})
    assert result["color"] == "yellow"
    assert result["minimum_color"] == "green"
    assert result["requires_review"]
    assert {item["rule_id"] for item in result["skipped_rules"]} == {
        "fever",
        "oxygen",
        "pain",
    }
    assert evaluate_triage({})["color"] == "yellow"


def test_output_does_not_share_mutable_evidence_with_inputs():
    data = prepared(questionnaire("nezadouci_ucinky", answer("pocit", "5", 4)))
    before = deepcopy(data)
    result = evaluate_checkin(data)
    result["non_green_answers"][0]["selected_options"][0]["text"] = "changed"
    reason(result, "overall_feeling")["evidence"][0]["value"] = "changed"
    assert data == before


@pytest.mark.parametrize(
    "field",
    [
        "chemotherapy_within_6_weeks",
        "pain_persists_after_rescue_dose",
        "suicide_plan_intent_or_means",
    ],
)
def test_context_requires_real_booleans(field):
    with pytest.raises(ValueError, match="bool or None"):
        evaluate_checkin(prepared(), {field: "false"})


def test_flat_fact_interface_remains_available():
    result = evaluate_triage({"temperature_c": 38, "chemotherapy_within_6_weeks": True})
    assert result["color"] == "red"
    assert result["requires_review"]


@pytest.mark.parametrize(
    "form,question,value,index",
    [
        ("nezadouci_ucinky", "dusnost", "Bez dušnosti", 0),
        ("nezadouci_ucinky", "bol_hrud", "Chronická bolest", 0),
        ("nezadouci_ucinky", "zvraceni", "1–2 epizody", 0),
        ("psychoonkologicky_screening", "sebevrazda", "Ne", 1),
        ("bolest_analgeticka_terapie", "sos", 2, None),
    ],
)
def test_non_triggering_answers_do_not_raise_severity(form, question, value, index):
    data = prepared(
        *neutral_forms(), questionnaire(form, answer(question, value, index))
    )
    result = evaluate_checkin(data)
    assert result["color"] == "green"
    assert result["reasons"] == []


@pytest.mark.parametrize("question,index", [("prujem", 3), ("zvraceni", 3)])
def test_answers_without_required_rule_details_remain_for_review(question, index):
    data = prepared(
        *neutral_forms(),
        questionnaire(
            "nezadouci_ucinky", answer(question, "Nejasné podrobnosti", index)
        ),
    )
    result = evaluate_checkin(data)
    assert result["color"] == "red"
    assert reason(result, f"unassessed_answer:nezadouci_ucinky:{question}")[
        "provisional"
    ]
    assert result["requires_review"]
    assert result["non_green_answers"]
    assert any(item["code"] == "unassessed_answer" for item in result["review_issues"])


def test_unsupported_measurements_and_attachments_remain_separate_from_color():
    data = prepared(*neutral_forms())
    data["vital_signs"]["unmapped_sensor"] = {"hodnota": 85, "zdroj": "synthetic"}
    data["attachments"] = [{"popis": "Syntetická příloha"}]
    result = evaluate_checkin(data)
    assert result["color"] == "yellow"
    codes = {item["code"] for item in result["review_issues"]}
    assert {"unassessed_measurement", "unassessed_attachments"} <= codes


def test_arbitrary_reference_fields_do_not_affect_triage():
    data = prepared(*neutral_forms())
    data.update(ground_truth={"uroven": 4}, nazev_scenare="Reference-only hint")
    result = evaluate_checkin(data, {"ground_truth": {"uroven": 4}})
    assert result["color"] == "green"
    assert result["reasons"] == []


def test_cli_accepts_prepared_checkin_and_context(tmp_path, monkeypatch, capsys):
    from meddi.triage import main

    data = prepared(
        questionnaire("nezadouci_ucinky", answer("teplota", "38–39 °C", 1)),
        temperature=None,
    )
    input_file = tmp_path / "prepared.json"
    context_file = tmp_path / "context.json"
    input_file.write_text(json.dumps(data), encoding="utf-8")
    context_file.write_text(
        json.dumps({"chemotherapy_within_6_weeks": True}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["triage", str(input_file), "--checkin", "--context", str(context_file)],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["color"] == "red"
    assert reason(result, "fever")["source"]
