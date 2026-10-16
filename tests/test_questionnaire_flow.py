"""Větvení testujeme deterministicky; tyto testy neměří porozumění LLM."""

import json

import pytest

from llm_intake import Intake, load_question
from llm_intake.client import Client
from llm_intake.core import DEFINITIONS, load_questions, validate
from llm_intake.flow import QuestionnaireFlow
from llm_intake.master_contract import Fact, MessageEvent
from llm_intake.pipeline import build_pipeline_packet
from llm_intake.question_catalog import load_catalog, lookup_questions


def answered(value, text="Syntetická odpověď."):
    return {
        "status": "answered",
        "value": value,
        "source_index": 0,
        "evidence": text,
        "follow_up": None,
    }


def confirmed(question, value):
    session = Intake(question, lambda *_: answered(value))
    session.submit("Syntetická odpověď.")
    session.confirm()
    return session


def record(flow, question_id, value):
    question = flow.next_question()
    assert question.id == question_id
    flow.record(confirmed(question, value))


@pytest.mark.parametrize(
    "form_id,count",
    [
        ("nezadouci_ucinky", 25),
        ("psychoonkologicky_screening", 9),
        ("bolest_analgeticka_terapie", 5),
        ("esas", 10),
    ],
)
def test_all_defined_questions_are_reachable_in_source_order(form_id, count):
    flow = QuestionnaireFlow(form_id)
    visited = []
    while question := flow.next_question():
        visited.append(question.id)
        if question.kind == "vice":
            value = [
                i
                for i in range(len(question.options))
                if i not in question.exclusive_options
            ]
        elif question.kind == "jedna":
            value = 1 if question.id == "krvaceni" else 0
        elif question.kind == "skala_1_10":
            value = 1
        elif question.kind == "cislo":
            value = 0
        else:
            value = "Syntetický popis."
        flow.record(confirmed(question, value))
    expected = [q.id for q in load_questions() if q.questionnaire_id == form_id]
    assert visited == expected
    assert len(visited) == count
    assert flow.snapshot()["state"] == "complete"


def test_no_side_effects_skips_all_descendants_without_fake_answers():
    flow = QuestionnaireFlow("nezadouci_ucinky")
    record(flow, "pocit", 0)
    record(flow, "sobestacnost", 0)
    record(flow, "ucinky", [12])
    assert flow.next_question() is None
    assert flow.snapshot()["state"] == "complete"
    assert all(q["state"] == "skipped" for q in flow.snapshot()["questions"][3:])
    assert len(flow.sessions) == 3


def test_multiselect_follows_only_selected_nested_branches():
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["ucinky"])
    record(flow, "ucinky", [0, 1, 7])
    record(flow, "nnz_typ", [2])
    record(flow, "zvraceni", 1)
    record(flow, "stolice_typ", [0])
    record(flow, "prujem", 0)
    record(flow, "unava", 1)
    assert flow.next_question() is None
    assert flow.snapshot()["state"] == "complete"
    assert [s.question.id for s in flow.sessions] == [
        "ucinky",
        "nnz_typ",
        "zvraceni",
        "stolice_typ",
        "prujem",
        "unava",
    ]


def test_targeted_entry_does_not_require_or_invent_parent_answers():
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["unava", "zvraceni"])
    record(flow, "zvraceni", 0)
    record(flow, "unava", 0)
    assert flow.snapshot()["targets"] == ["zvraceni", "unava"]
    assert flow.snapshot()["state"] == "complete"
    assert [s.question.id for s in flow.sessions] == ["zvraceni", "unava"]


@pytest.mark.parametrize("value,expected_next", [(0, None), (1, "krvaceni_popis")])
def test_targeted_entry_still_obeys_its_descendant_condition(value, expected_next):
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["krvaceni"])
    record(flow, "krvaceni", value)
    question = flow.next_question()
    assert (question.id if question else None) == expected_next


def test_target_does_not_override_negative_parent_inside_scope():
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["ucinky", "zvraceni"])
    record(flow, "ucinky", [12])
    assert flow.next_question() is None
    assert not any(s.question.id == "zvraceni" for s in flow.sessions)


def test_unconfirmed_parent_does_not_activate_branch():
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["krvaceni"])
    session = Intake(flow.next_question(), lambda *_: answered(1))
    session.submit("Syntetická odpověď.")
    with pytest.raises(ValueError):
        flow.record(session)
    assert flow.next_question().id == "krvaceni"


def test_unresolved_parent_leaves_descendant_blocked():
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["krvaceni"])
    session = Intake(
        flow.next_question(),
        lambda *_: {
            "status": "unclear",
            "value": None,
            "source_index": None,
            "evidence": None,
            "follow_up": "Objevilo se krvácení?",
        },
        max_clarifications=0,
    )
    session.submit("Nevím.")
    flow.record(session)
    assert flow.next_question() is None
    assert flow.snapshot()["state"] == "blocked"
    assert flow.snapshot()["questions"][-1]["state"] == "blocked"


def test_out_of_order_session_is_rejected():
    flow = QuestionnaireFlow("nezadouci_ucinky")
    session = confirmed(load_question("nezadouci_ucinky", "unava"), 0)
    with pytest.raises(ValueError):
        flow.record(session)


@pytest.mark.parametrize(
    "condition", ["missing:0", "ucinky:99", "zvraceni:0", "ucinky:0:1"]
)
def test_invalid_or_forward_condition_fails_explicitly(tmp_path, condition):
    forms = json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    forms[0]["otazky"][3]["podminka"] = condition
    path = tmp_path / "definitions.json"
    path.write_text(json.dumps(forms), encoding="utf-8")
    with pytest.raises(ValueError):
        QuestionnaireFlow("nezadouci_ucinky", path=path)


def test_same_question_package_in_catalog_and_actual_model_request():
    question = load_question("nezadouci_ucinky", "ucinky")
    catalog = load_catalog()
    assert catalog[(question.questionnaire_id, question.id)] == question.specification()
    payload = Client("synthetic-test-key").payload(question, ["Únava."])
    spec = json.loads(payload["messages"][-1]["content"])["question"]
    assert spec == question.specification()
    assert len(spec["options"]) == 13
    assert spec["exclusive_option_indices"] == [12]
    assert "barva" not in json.dumps(spec)
    assert "upozorneni" not in json.dumps(spec)
    assert load_question("esas", "bolest").questionnaire_note
    assert "zelena" not in question.patient_options()


def test_catalog_sorts_candidates_by_definition_order():
    result = lookup_questions(["fatigue", "vomiting"])
    assert [q["question_id"] for q in result["questions"]] == ["zvraceni", "unava"]


@pytest.mark.parametrize("value", [[12, 0], [7, 12]])
def test_none_cannot_be_combined_with_side_effect(value):
    with pytest.raises(ValueError):
        validate(
            load_question("nezadouci_ucinky", "ucinky"),
            answered(value),
            ["Syntetická odpověď."],
        )


@pytest.mark.parametrize("targets", [[], ["nezname_id"], "unava"])
def test_invalid_target_selection_is_explicit(targets):
    with pytest.raises((TypeError, ValueError)):
        QuestionnaireFlow("nezadouci_ucinky", targets=targets)


def test_model_package_keeps_scale_direction_without_color_mapping():
    question = load_question("esas", "bolest")
    assert "1 = nejlépe" in question.questionnaire_note
    assert "10 = nejhůře" in question.questionnaire_note
    assert "barevný" not in question.questionnaire_note
    assert "červená" not in question.questionnaire_note


def test_few_shot_questions_are_resolved_from_same_definitions():
    payload = Client("synthetic-test-key").payload(
        load_question("nezadouci_ucinky", "unava"), ["Pomůže."]
    )
    examples = payload["messages"][1:-1:2]
    assert len(examples) == 3
    for example in examples:
        package = json.loads(example["content"])["question"]
        assert (
            package
            == load_question(
                package["questionnaire_id"], package["question_id"]
            ).specification()
        )


def event():
    return MessageEvent(
        id="synthetic-master",
        patient_id="synthetic-patient",
        text="Jsem unavený.",
        available_at="2026-10-16T10:00:00+02:00",
        source="master_question",
        author="patient",
        question="Jak se dnes cítíte?",
    )


def test_pipeline_preserves_values_and_dialogue_without_color():
    flow = QuestionnaireFlow("nezadouci_ucinky", targets=["unava"])
    record(flow, "unava", 1)
    packet = build_pipeline_packet(
        event(), [Fact("fatigue", "present", "unavený", "patient")], flow.sessions
    )
    assert json.loads(json.dumps(packet, allow_nan=False)) == packet
    assert packet["kind"] == "llm_intake"
    assert packet["schema_version"] == 1
    assert packet["facts"][0]["confirmation"] == "unconfirmed"
    answer = packet["question_answers"][0]
    assert answer["confirmed"] is True
    assert answer["value"] == 1
    assert answer["question"]["question_id"] == "unava"
    assert answer["turns"][0]["question"] == flow.sessions[0].question.text
    assert answer["evidence"]["turn_index"] == 0
    assert "barva" not in json.dumps(packet)
    assert "signaly_odpovedi" not in json.dumps(packet)
    packet["question_answers"][0]["turns"].clear()
    assert len(flow.sessions[0].snapshot()["source_messages"]) == 1


def test_rejected_draft_is_not_exported_as_current_answer():
    session = Intake(load_question("nezadouci_ucinky", "unava"), lambda *_: answered(0))
    session.submit("Syntetická odpověď.")
    draft = build_pipeline_packet(event(), [], [session])["question_answers"][0]
    assert draft["value"] == 0 and draft["confirmed"] is False
    session.reject()
    rejected = build_pipeline_packet(event(), [], [session])["question_answers"][0]
    assert rejected["state"] == "needs_correction"
    assert rejected["value"] is None
    assert rejected["answer"] is None
    assert rejected["evidence"] is None
    assert rejected["turns"]


def test_duplicate_question_in_one_packet_is_rejected():
    session = confirmed(load_question("nezadouci_ucinky", "unava"), 0)
    with pytest.raises(ValueError):
        build_pipeline_packet(event(), [], [session, session])


def test_cli_offers_plain_options_without_calling_model_for_help(monkeypatch, capsys):
    from llm_intake.__main__ import main

    calls = []

    def extract(*args):
        calls.append(args)
        return answered([7], "Únava a slabost")

    monkeypatch.setattr(Client, "from_env", lambda: extract)
    monkeypatch.setattr("sys.argv", ["llm_intake", "--question", "ucinky"])
    responses = iter(["/moznosti", "Únava a slabost", "ano"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    assert main() == 0
    output = capsys.readouterr().out
    assert "- Únava a slabost" in output
    assert len(calls) == 1
    assert calls[0][1] == ["Únava a slabost"]
    assert "zelena" not in output


def test_find_question_resolves_unique_and_handles_collisions():
    from llm_intake import find_question

    q_zvraceni = find_question("zvraceni")
    assert q_zvraceni.questionnaire_id == "nezadouci_ucinky"
    assert q_zvraceni.id == "zvraceni"

    q_nrs = find_question("nrs")
    assert q_nrs.questionnaire_id == "bolest_analgeticka_terapie"

    # Duplicitní ID mezi dotazníky vyžaduje upřesnění
    with pytest.raises(ValueError, match="definována ve více dotaznících"):
        find_question("unava")

    q_unava_esas = find_question("unava", questionnaire_id="esas")
    assert q_unava_esas.questionnaire_id == "esas"

    with pytest.raises(ValueError, match="Neznámá otázka"):
        find_question("neexistujici_otazka")


def test_flow_for_targets_infers_questionnaire():
    flow = QuestionnaireFlow.for_targets(["zvraceni"])
    assert flow.questionnaire_id == "nezadouci_ucinky"
    assert flow.next_question().id == "zvraceni"

    with pytest.raises(TypeError):
        QuestionnaireFlow.for_targets("zvraceni")

    with pytest.raises(ValueError):
        QuestionnaireFlow.for_targets([])


def test_create_targeted_session_runs_intake_smoothly():
    from llm_intake import create_targeted_session

    text = "Zvracel jsem asi 4x."
    session = create_targeted_session("zvraceni", lambda *_: answered(1, text=text))
    assert session.question.id == "zvraceni"
    session.submit(text)
    assert session.state == "needs_confirmation"
    confirmed_data = session.confirm()
    assert confirmed_data["odpoved_index"] == 1
    assert confirmed_data["confirmed"] is True


def test_all_public_api_symbols_available_from_package_root():
    import llm_intake

    expected_symbols = [
        "Fact",
        "Intake",
        "MasterDialogue",
        "MasterExtractor",
        "MessageEvent",
        "NumericRange",
        "Question",
        "QuestionnaireFlow",
        "analyze_message",
        "build_packet",
        "build_pipeline_packet",
        "create_targeted_session",
        "find_question",
        "load_catalog",
        "load_question",
        "load_questions",
        "load_topic_catalog",
        "lookup_questions",
        "resolve_topics",
    ]
    for symbol in expected_symbols:
        assert hasattr(llm_intake, symbol), f"Symbol {symbol} chybí v llm_intake"
