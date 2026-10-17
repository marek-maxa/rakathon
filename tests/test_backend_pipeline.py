"""Backend integration with synthetic inputs, no network or model calls."""

import json
from copy import deepcopy
from dataclasses import asdict
from itertools import permutations

import pytest

from llm_intake.core import Intake, load_question
from llm_intake.dialogue import MasterDialogue
from llm_intake.master_contract import Fact, MessageEvent
from llm_intake.pipeline import build_pipeline_packet
from meddi.form import prepare_checkin
from meddi.pipeline import evaluate_contact, main
from meddi.triage import evaluate_checkin, fever_score, oxygen_score
from triage import evaluate_pipeline_packet

TIME = "2026-10-17T10:00:00+02:00"
OLD = "2026-10-16T10:00:00+02:00"
FUTURE = "2026-10-18T10:00:00+02:00"


def event(text="Syntetická odpověď.", id="synthetic", at=TIME):
    return MessageEvent(
        id,
        "synthetic-patient",
        text,
        at,
        "master_question",
        "patient",
        "Jak se dnes cítíte?",
    )


def packet(concept="temperature", value=38.2, unit="degC", **changes):
    time_text = changes.get("time_text")
    message = event("Syntetická odpověď." + (f" {time_text}" if time_text else ""))
    fact = Fact(
        concept, "present", message.text, "patient", value=value, unit=unit, **changes
    )
    return build_pipeline_packet(message, [fact])


def test_degc_reaches_shared_fever_rule_with_provenance_and_no_confirmation():
    source = packet()
    result = evaluate_contact(source, context={"chemotherapy_within_6_weeks": True})
    assert result["color"] == result["minimum_color"] == "red"
    assert result["assessment_status"] == "incomplete"
    assert result["scores"]["fever"] == 4
    assert result["intake"] == source
    assert not source["question_answers"]
    assert any(r["rule_id"] == "reported_fever" for r in result["reasons"])
    sources = result["triage_inputs"]["observations"]["temperature_c"]
    assert sources[0]["source"]["source_message_id"] == source["message"]["id"]
    assert sources[0]["source"]["confirmation"] == "unconfirmed"
    assert (
        evaluate_pipeline_packet(source, {"chemotherapy_within_6_weeks": True})
        == result
    )


def test_current_conflicts_keep_worst_rule_independent_of_input_order():
    source = packet(value=36.5)
    source["facts"].append({**source["facts"][0], "value": 39})
    for facts in permutations(source["facts"]):
        result = evaluate_contact(
            {**source, "facts": list(facts)},
            context={"chemotherapy_within_6_weeks": True},
        )
        assert result["color"] == "red"
        assert any(
            i["code"] == "conflicting_current_values" for i in result["adapter_issues"]
        )
        assert {
            r["value"] for r in result["triage_inputs"]["observations"]["temperature_c"]
        } == {36.5, 39}


def test_current_glucose_conflicts_keep_low_and_high_not_just_maximum():
    source = packet("glucose_mmol_l", 2, "mmol/l")
    source["facts"].append({**source["facts"][0], "value": 20})
    result = evaluate_contact(source, context={"insulin_treatment": True})
    assert result["color"] == "orange"
    assert result["scores"]["hypoglycemia_on_insulin"] == 3
    assert len(result["triage_inputs"]["observations"]["glucose_mmol_l"]) == 2


def test_newer_normal_measurement_does_not_permanently_keep_old_red():
    old, new = event(id="old", at=OLD), event(id="new")
    source = packet(value=36.5)
    source["message"] = asdict(old)
    source["messages"] = [asdict(old), asdict(new)]
    source["facts"] = [
        {**source["facts"][0], "source_message_id": "old", "value": 39},
        {**source["facts"][0], "source_message_id": "new", "value": 36.5},
    ]
    for facts in permutations(source["facts"]):
        result = evaluate_contact(
            {**source, "facts": list(facts)},
            context={"chemotherapy_within_6_weeks": True},
        )
        assert result["color"] == "green"
        assert result["minimum_color"] == "green"
        assert [
            r["value"] for r in result["triage_inputs"]["observations"]["temperature_c"]
        ] == [36.5]


def test_fresh_fact_overrides_older_card_measurement_not_reverse():
    snapshot = {
        "patient_id": "synthetic-patient",
        "as_of": OLD,
        "context": {"chemotherapy_within_6_weeks": True},
        "observations": {"temperature_c": {"value": 36.5, "unit": "C"}},
    }
    result = evaluate_contact(packet(), snapshot)
    assert result["color"] == "red"
    assert [
        r["value"] for r in result["triage_inputs"]["observations"]["temperature_c"]
    ] == [38.2]


def test_confirmed_current_temperature_range_supersedes_older_measurement():
    old, new = event(id="old", at=OLD), event(id="new")
    source = packet(value=39)
    source.update(message=asdict(old), messages=[asdict(old), asdict(new)])
    source["facts"][0]["source_message_id"] = "old"
    source["question_answers"] = [
        {
            "question": {
                "questionnaire_id": "nezadouci_ucinky",
                "question_id": "teplota",
            },
            "state": "confirmed",
            "confirmed": True,
            "value": 0,
            "turns": [{"available_at": TIME, "source_message_id": "new"}],
        }
    ]
    result = evaluate_contact(source, context={"chemotherapy_within_6_weeks": True})
    assert result["minimum_color"] == "green"
    assert not result["triage_inputs"]["observations"].get("temperature_c")


def test_count_with_explicit_day_window_reaches_vomiting_red_rule():
    source = packet(
        "vomiting.episodes", 6, "episodes", time_text="za posledních 24 hodin"
    )
    source["message"]["text"] = "Syntetická odpověď. za posledních 24 hodin"
    result = evaluate_contact(source)
    assert result["color"] == "red"
    assert result["scores"]["vomiting"] == 4


@pytest.mark.parametrize(
    "concept, value, unit, question, choice, time_text",
    [
        ("temperature", 38.2, "degC", "teplota", 1, None),
        ("overall_feeling", 5, None, "pocit", 4, None),
        ("vomiting.episodes", 6, "episodes", "zvraceni", 2, "24h"),
    ],
)
def test_matching_fact_and_confirmed_choice_are_not_false_conflicts(
    concept, value, unit, question, choice, time_text
):
    source = packet(concept, value, unit, time_text=time_text)
    source["question_answers"] = [
        {
            "question": {
                "questionnaire_id": "nezadouci_ucinky",
                "question_id": question,
            },
            "state": "confirmed",
            "confirmed": True,
            "value": choice,
        }
    ]
    result = evaluate_contact(source)
    assert not any(
        i["code"] == "conflicting_current_values" for i in result["adapter_issues"]
    )


def test_contradicting_temperature_choice_and_measurement_keep_red_rule():
    source = packet(value=39)
    source["question_answers"] = [
        {
            "question": {
                "questionnaire_id": "nezadouci_ucinky",
                "question_id": "teplota",
            },
            "confirmed": True,
            "value": 0,
        }
    ]
    result = evaluate_contact(source, context={"chemotherapy_within_6_weeks": True})
    assert result["color"] == "red"
    assert any(i["code"] == "conflicting_temperature" for i in result["review_issues"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"time_text": "Od rána"},
        {
            "value": {
                "lower": 5,
                "upper": 6,
                "lower_inclusive": True,
                "upper_inclusive": True,
            }
        },
    ],
)
def test_no_invented_24h_or_exact_count(kwargs):
    source = packet("vomiting.episodes", 2, "episodes")
    source["facts"][0].update(kwargs)
    if kwargs.get("time_text"):
        source["message"]["text"] += " " + kwargs["time_text"]
    result = evaluate_contact(source)
    assert result["color"] == "yellow"
    assert result["doporuceny_krok"] == "kontaktovat_tym"
    assert result["unprocessed_facts"]
    assert "vomiting_episodes_24h" not in result["triage_inputs"]["observations"]


def test_total_stools_do_not_become_increase_above_baseline():
    source = packet("diarrhea.episodes", 8, "episodes", time_text="24h")
    result = evaluate_contact(source, context={"immunotherapy": True})
    assert result["color"] == "yellow"
    assert "stools_above_baseline_24h" not in result["triage_inputs"]["observations"]


def test_symptom_outside_question_catalogue_is_still_evaluated():
    result = evaluate_contact(packet("confusion", None, None))
    assert result["color"] == "red"
    assert result["scores"]["neurological_red_flags"] == 4


def test_latest_explicit_negation_replaces_prior_symptom_without_inventing_zero():
    source = packet("confusion", None, None)
    source["messages"] = [asdict(event(id="old", at=OLD)), asdict(event())]
    source["facts"] = [
        {**source["facts"][0], "source_message_id": "old"},
        {**source["facts"][0], "presence": "absent"},
    ]
    result = evaluate_contact(source)
    assert result["color"] == "yellow"
    assert not any(r["color"] == "red" for r in result["reasons"])
    assert result["triage_inputs"]["observations"]["confusion"][0]["value"] is False


@pytest.mark.parametrize("subject", ["caregiver", "unknown"])
def test_patient_rules_do_not_consume_someone_elses_symptom(subject):
    source = packet("confusion", None, None)
    source["facts"][0]["subject"] = subject
    result = evaluate_contact(source)
    assert result["color"] == "yellow"
    assert result["unprocessed_facts"][0]["reason"] == "other_or_unknown_subject"


def test_future_message_is_not_decision_input():
    source = packet()
    source["message"]["available_at"] = FUTURE
    result = evaluate_contact(
        source, context={"chemotherapy_within_6_weeks": True}, now=TIME
    )
    assert result["color"] == "yellow"
    assert not result["triage_inputs"]["observations"]
    assert result["deferred_inputs"][0]["reason"] == "future_input"


@pytest.mark.parametrize("field", ["evidence", "time_text"])
def test_fabricated_citation_is_rejected_at_backend_boundary(field):
    source = packet()
    source["facts"][0][field] = "Toto pacient neřekl."
    with pytest.raises(ValueError):
        evaluate_contact(source)


@pytest.mark.parametrize(
    "record, reason",
    [
        ({"value": True, "available_at": FUTURE}, "future_input"),
        ({"value": True, "valid_until": OLD}, "expired_input"),
    ],
)
def test_future_or_expired_context_is_not_treatment_evidence(record, reason):
    result = evaluate_contact(packet(), context={"chemotherapy_within_6_weeks": record})
    assert result["color"] == "red"
    assert all(item["provisional"] for item in result["reasons"])
    assert result["deferred_inputs"][0]["reason"] == reason
    assert not result["triage_inputs"]["context"]


def test_inconsistent_observed_time_cannot_be_available_before_it_occurs():
    source = packet()
    source["facts"][0]["observed_at"] = FUTURE
    with pytest.raises(ValueError):
        evaluate_contact(source)


@pytest.mark.parametrize(
    "snapshot",
    [
        {"patient_id": "someone-else", "as_of": TIME},
        {"patient_id": "synthetic-patient", "as_of": FUTURE},
        {"patient_id": "synthetic-patient", "as_of": "2026-10-17T10:00:00"},
        {"patient_id": "synthetic-patient", "as_of": TIME, "checkiny": []},
    ],
)
def test_snapshot_identity_time_and_scope_are_explicit(snapshot):
    with pytest.raises(ValueError):
        evaluate_contact(packet(), snapshot)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, -1])
def test_invalid_temperature_rejected_through_every_backend_path(value):
    source = packet()
    source["facts"][0]["value"] = value
    with pytest.raises(ValueError):
        evaluate_contact(source)
    with pytest.raises(ValueError):
        fever_score(value, True)
    raw = {"dotazniky": [], "vitalni_funkce": {"teplota_c": {"hodnota": value}}}
    with pytest.raises(ValueError):
        prepare_checkin(raw)
    with pytest.raises(ValueError):
        evaluate_checkin({"answers": [], "vital_signs": raw["vitalni_funkce"]})


@pytest.mark.parametrize("value", [101, -1, True, float("nan")])
def test_invalid_saturation_rejected(value):
    with pytest.raises(ValueError):
        oxygen_score(value)


def test_chronic_chest_pain_remains_present_for_combined_rule():
    prepared = prepare_checkin(
        {
            "dotazniky": [
                {
                    "dotaznik_id": "nezadouci_ucinky",
                    "odpovedi": [
                        {
                            "otazka_id": "bol_hrud",
                            "odpoved_index": 0,
                            "odpoved": "Dlouhodobá bolest",
                        }
                    ],
                }
            ]
        }
    )
    result = evaluate_checkin(prepared, observations={"high_blood_pressure": True})
    assert result["color"] == "red"
    assert result["scores"]["hypertension_with_warning_signs"] == 4
    assert result["scores"]["new_chest_pain"] == 1


def test_intake_replay_to_backend_and_json_roundtrip(tmp_path, monkeypatch):
    message = event("Za posledních 24 hodin jsem zvracel šestkrát.")
    fact = Fact(
        "vomiting.episodes",
        "present",
        message.text,
        "patient",
        value=6,
        unit="episodes",
        time_text="Za posledních 24 hodin",
    )
    extract = lambda *_: {
        "status": "answered",
        "value": 2,
        "source_index": 0,
        "evidence": message.text,
        "follow_up": None,
    }
    contact = MasterDialogue(lambda _: [fact], extract)
    before_confirmation = contact.start(message)
    assessment = evaluate_contact(before_confirmation)
    assert assessment["color"] == "red"  # Already before patient's confirmation.
    assert not assessment["intake"]["question_answers"][0]["confirmed"]
    confirmed = contact.confirm()
    source_path, dest = tmp_path / "packet.json", tmp_path / "assessment.json"
    source_path.write_text(json.dumps(confirmed), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["pipeline", str(source_path), "--output", str(dest)]
    )
    main()
    stored = json.loads(dest.read_text(encoding="utf-8"))
    assert stored["color"] == "red"
    assert stored["intake"]["question_answers"][0]["confirmed"]
    assert stored["intake"]["messages"][0]["id"] == message.id


def test_rejected_proposal_never_becomes_confirmed_rule_input():
    message = event()
    session = Intake(
        load_question("nezadouci_ucinky", "pocit"),
        lambda *_: {
            "status": "answered",
            "value": 4,
            "source_index": 0,
            "evidence": message.text,
            "follow_up": None,
        },
    )
    session.submit(message.text)
    session.reject()
    result = evaluate_contact(build_pipeline_packet(message, [], [session]))
    assert result["color"] == "yellow"
    assert not result["triage_inputs"]["prepared"]["answers"]


def test_inputs_and_raw_facts_survive_unchanged_without_shared_mutation():
    source = packet()
    before = deepcopy(source)
    result = evaluate_contact(source)
    assert source == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    result["intake"]["facts"][0]["value"] = 0
    assert source == before
