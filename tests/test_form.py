"""Questionnaire evidence preparation with synthetic patient answers."""

import json
from copy import deepcopy

import pytest

from meddi.common_types import Severity
from meddi.form import QUESTIONNAIRE_DEFINITIONS, evaluate_checkin, prepare_checkin


def questionnaire(identifier, *answers):
    return {
        "dotaznik_id": identifier,
        "vyplneni_id": "synthetic-form",
        "odpovedi": list(answers),
    }


def answer(identifier, value=None, index=None):
    return {"otazka_id": identifier, "odpoved": value, "odpoved_index": index}


def checkin(*questionnaires):
    return {
        "patient_id": "synthetic-patient",
        "checkin_id": "synthetic-checkin",
        "datum": "2026-10-16",
        "cas": "12:00",
        "den_sledovani": 2,
        "cyklus": 1,
        "den_cyklu": 2,
        "stav": "vyplneno",
        "vyplnil": "dcera",
        "dotazniky": list(questionnaires),
        "vitalni_funkce": {"teplota_c": {"hodnota": 38.2, "zdroj": "teplomer"}},
        "zprava_pacienta": "Nemůžu pít.",
        "prilohy": [{"popis": "syntetická příloha"}],
    }


def test_prepares_traceable_non_green_answers_from_definitions():
    fever = answer("teplota", "Pacientem uvedené rozmezí", 1)
    # Cached labels must not override the definition selected by the index.
    fever.update(barva="zelena", otazka="Zastaralá otázka", upozorneni="Stará zpráva")
    source = checkin(questionnaire("nezadouci_ucinky", answer("pocit", "1", 0), fever))
    result = prepare_checkin(source)

    assert len(result["answers"]) == 2  # Keep green answers as evidence too.
    (warning_answer,) = result["non_green_answers"]
    assert warning_answer["questionnaire_id"] == "nezadouci_ucinky"
    assert warning_answer["questionnaire_instance_id"] == "synthetic-form"
    assert warning_answer["question_id"] == "teplota"
    assert warning_answer["condition"] == "ucinky:5"
    assert warning_answer["value"] == fever["odpoved"]
    assert warning_answer["option_indices"] == 1
    assert warning_answer["color"] == "yellow"
    definition = next(
        question
        for question in QUESTIONNAIRE_DEFINITIONS["nezadouci_ucinky"]["otazky"]
        if question["id"] == "teplota"
    )
    assert warning_answer["question"] == definition["text"]
    assert warning_answer["selected_options"] == [
        {
            "index": 1,
            "text": definition["moznosti"][1]["text"],
            "color": "yellow",
            "warning": definition["moznosti"][1]["upozorneni"],
        }
    ]
    assert evaluate_checkin(source) == Severity.YELLOW


def test_keeps_uncolored_choices_numbers_and_text_without_inference():
    source = checkin(
        questionnaire(
            "nezadouci_ucinky",
            answer("ucinky", ["Jiné"], [11]),
            answer("jine", "Bolí mě při polykání."),
        ),
        questionnaire(
            "bolest_analgeticka_terapie",
            answer("nrs", 8),
            answer("sos", 3),
            answer("nu", ["Zácpa", "Jiné"], [0, 3]),
        ),
        questionnaire("psychoonkologicky_screening", answer("sebevrazda", "Ano", 0)),
    )
    result = prepare_checkin(source)
    assert [item["value"] for item in result["answers"]] == [
        ["Jiné"],
        "Bolí mě při polykání.",
        8,
        3,
        ["Zácpa", "Jiné"],
        "Ano",
    ]
    assert all(item["color"] is None for item in result["answers"])
    assert result["answers"][2]["note"] == "Formulář nabízí pouze 1–10."
    assert result["answers"][5]["questionnaire_note"]
    assert result["non_green_answers"] == []
    assert [option["index"] for option in result["answers"][4]["selected_options"]] == [
        0,
        3,
    ]
    assert evaluate_checkin(source) is None
    assert "pain_persists_after_rescue_dose" not in result
    assert "color" not in result  # Final severity belongs to triage.


@pytest.mark.parametrize(
    "value,color",
    [
        (1, "green"),
        (3, "green"),
        (4, "yellow"),
        (5, "yellow"),
        (6, "red"),
        (10, "red"),
        (None, None),
    ],
)
def test_esas_display_colors_and_shared_question_ids(value, color):
    result = prepare_checkin(
        checkin(
            questionnaire("esas", answer("unava", value)),
            questionnaire("nezadouci_ucinky", answer("unava", "Ano.", 0)),
        )
    )
    assert len(result["answers"]) == 2
    assert result["answers"][0]["color"] == color
    assert result["answers"][0]["instructions"]
    assert result["answers"][1]["color"] == "green"
    assert len(result["non_green_answers"]) == int(color in ("yellow", "red"))


def test_preserves_context_without_mutating_inputs_or_definitions():
    source = checkin(
        questionnaire("nezadouci_ucinky", answer("ucinky", ["Únava"], [7]))
    )
    before = deepcopy(source)
    definitions_before = deepcopy(QUESTIONNAIRE_DEFINITIONS)
    result = prepare_checkin(source)
    assert result["date"] == "2026-10-16"
    assert result["time"] == "12:00"
    assert result["patient_id"] == "synthetic-patient"
    assert result["checkin_id"] == "synthetic-checkin"
    assert (result["monitoring_day"], result["cycle"], result["cycle_day"]) == (2, 1, 2)
    assert result["status"] == "vyplneno"
    assert result["filled_by"] == "dcera"
    assert result["patient_message"] == source["zprava_pacienta"]
    assert result["vital_signs"] == source["vitalni_funkce"]
    assert result["attachments"] == source["prilohy"]
    assert json.loads(json.dumps(result, ensure_ascii=False)) == result
    result["answers"][0]["value"].append("changed")
    result["answers"][0]["option_indices"].append(1)
    result["answers"][0]["selected_options"][0]["text"] = "changed"
    result["vital_signs"]["teplota_c"]["hodnota"] = 0
    result["attachments"][0]["popis"] = "changed"
    assert source == before
    assert QUESTIONNAIRE_DEFINITIONS == definitions_before


def test_missing_answers_and_context_stay_unknown():
    result = prepare_checkin(
        {
            "dotazniky": [
                questionnaire(
                    "nezadouci_ucinky", answer("pocit"), answer("ucinky", [], [])
                )
            ]
        }
    )
    assert result["answers"][0]["value"] is None
    assert result["answers"][0]["option_indices"] is None
    assert result["answers"][1]["value"] == []
    assert result["answers"][1]["option_indices"] == []
    assert result["non_green_answers"] == []
    assert result["vital_signs"] is None
    assert result["patient_message"] is None
    assert prepare_checkin({"dotazniky": []})["answers"] == []


@pytest.mark.parametrize("index", [-1, 99, True, "1", [1]])
def test_rejects_invalid_single_choice_indices(index):
    with pytest.raises(ValueError, match="Invalid option index"):
        prepare_checkin(
            checkin(questionnaire("nezadouci_ucinky", answer("pocit", index=index)))
        )


@pytest.mark.parametrize("value", [0, 11, True, "6", 4.5])
def test_rejects_invalid_esas_scores(value):
    with pytest.raises(ValueError, match="Invalid ESAS score"):
        prepare_checkin(checkin(questionnaire("esas", answer("bolest", value))))


def test_rejects_unknown_questions_and_invalid_multiple_choice_shape():
    with pytest.raises(ValueError, match="Unknown question"):
        prepare_checkin(checkin(questionnaire("esas", answer("unknown", 4))))
    with pytest.raises(ValueError, match="Expected a list"):
        prepare_checkin(
            checkin(questionnaire("nezadouci_ucinky", answer("ucinky", index=1)))
        )


def test_multiple_choice_retains_each_option_color_and_warning(monkeypatch):
    definition = {
        "id": "synthetic",
        "nazev": "Synthetic questionnaire",
        "otazky": [
            {
                "id": "symptoms",
                "text": "Synthetic question",
                "typ": "vice",
                "moznosti": [
                    {"text": "First", "barva": "zluta", "upozorneni": "First warning"},
                    {
                        "text": "Second",
                        "barva": "cervena",
                        "upozorneni": "Second warning",
                    },
                    {"text": "Third", "barva": None, "upozorneni": None},
                ],
            }
        ],
    }
    monkeypatch.setitem(QUESTIONNAIRE_DEFINITIONS, "synthetic", definition)
    result = prepare_checkin(
        checkin(
            questionnaire(
                "synthetic", answer("symptoms", ["First", "Second", "Third"], [0, 1, 2])
            )
        )
    )
    (item,) = result["non_green_answers"]
    assert item["color"] == "red"
    assert [option["color"] for option in item["selected_options"]] == [
        "yellow",
        "red",
        None,
    ]
    assert [option["warning"] for option in item["selected_options"]] == [
        "First warning",
        "Second warning",
        None,
    ]


def test_does_not_copy_reference_or_scenario_fields_into_evidence():
    source = checkin()
    source.update(ground_truth={"uroven": 4}, nazev_scenare="reference-only hint")
    result = prepare_checkin(source)
    assert "ground_truth" not in result
    assert "nazev_scenare" not in result
