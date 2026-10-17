import json
from dataclasses import asdict

import pytest

from llm_intake.client import APIError, Client
from llm_intake.core import load_questions
from llm_intake.dialogue import MasterDialogue
from llm_intake.evaluate_topics import CASES, evaluate_case, summarize
from llm_intake.master import (
    MasterExtractor,
    analyze_message,
    load_schema,
    validate_facts,
)
from llm_intake.master_contract import Fact, MessageEvent
from llm_intake.question_catalog import TOPICS, load_topic_catalog, resolve_topics


def event(text="Syntetické sdělení."):
    return MessageEvent(
        "synthetic-topics",
        "synthetic-patient",
        text,
        "2026-10-16T10:00:00+02:00",
        "master_question",
        "patient",
        "Jak se dnes cítíte?",
    )


TOPIC_IDS = [f"{q.questionnaire_id}/{q.id}" for q in load_questions()]


@pytest.mark.parametrize("topic_id", TOPIC_IDS)
def test_every_question_has_keywords_context_schema_id_and_mechanical_route(topic_id):
    catalogue = load_topic_catalog()
    row = catalogue[topic_id]
    assert row["keywords"] and row["hint"]
    assert (
        row["topic_id"]
        == f"{row['question']['questionnaire_id']}/{row['question']['question_id']}"
    )
    enum = load_schema()["properties"]["facts"]["items"]["properties"]["topic_ids"][
        "items"
    ]["enum"]
    assert topic_id in enum
    # Libovolný název faktu: směrování musí řídit právě validované ID tématu.
    fact = Fact(
        "reported_finding",
        "present",
        "Syntetické sdělení",
        "patient",
        topic_ids=(topic_id,),
    )
    packet = analyze_message(event(), lambda _: [fact])
    refs = [
        f"{c['question']['questionnaire_id']}/{c['question']['question_id']}"
        for c in packet["question_candidates"]
    ]
    assert topic_id in refs
    assert all(c["fact_indices"] == [0] for c in packet["question_candidates"])
    assert packet["facts"][0]["topic_ids"] == [topic_id]


@pytest.mark.parametrize("mutation", ["missing", "extra", "empty_keywords"])
def test_catalogue_drift_fails_instead_of_omitting_question(tmp_path, mutation):
    data = json.loads(TOPICS.read_text(encoding="utf-8"))
    if mutation == "missing":
        del data[TOPIC_IDS[0]]
    elif mutation == "extra":
        data["wrong/question"] = data[TOPIC_IDS[0]]
    else:
        data[TOPIC_IDS[0]]["keywords"] = []
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_topic_catalog(topics_path=path)


def test_prompt_contains_all_questions_and_no_top_k_subset():
    payload = MasterExtractor(Client("synthetic-key")).payload(event())
    actual = json.loads(payload["messages"][-1]["content"])
    rows = actual["topic_catalog"]
    assert [r["topic_id"] for r in rows] == TOPIC_IDS
    assert all(r["keywords"] and "options" in r["question"] for r in rows)


@pytest.mark.parametrize(
    "topic_ids",
    [["wrong/id"], [TOPIC_IDS[0], TOPIC_IDS[0]], "nezadouci_ucinky/unava", [False]],
)
def test_model_cannot_invent_or_duplicate_topic_ids(topic_ids):
    item = asdict(Fact("reported_finding", "present", "Syntetické sdělení", "patient"))
    item["topic_ids"] = topic_ids
    with pytest.raises(ValueError):
        validate_facts({"facts": [item]}, event())


def test_negative_and_caregiver_topics_are_retained_without_patient_questions():
    topic = "nezadouci_ucinky/kuze"
    facts = [
        Fact(
            "skin_symptoms",
            "absent",
            "Syntetické sdělení",
            "patient",
            topic_ids=(topic,),
        ),
        Fact(
            "fatigue",
            "present",
            "Syntetické sdělení",
            "caregiver",
            topic_ids=("nezadouci_ucinky/unava",),
        ),
    ]
    result = analyze_message(event(), lambda _: facts)
    assert not result["question_candidates"]
    assert len(result["facts"]) == 2
    assert all(f["topic_ids"] for f in result["facts"])


def test_binary_parent_cannot_be_bypassed_by_selecting_only_description():
    packages = resolve_topics(["nezadouci_ucinky/krvaceni_popis"])
    assert [q["question_id"] for q in packages] == ["krvaceni", "krvaceni_popis"]


def test_analgesic_other_effects_keep_source_parent_condition():
    packages = resolve_topics(["bolest_analgeticka_terapie/nu_jine"])
    assert [q["question_id"] for q in packages] == ["nu", "nu_jine"]
    assert packages[1]["condition"] == "nu:3"


def test_unknown_detail_is_not_hidden_by_generic_other_question():
    fact = Fact(
        "confusion",
        "present",
        "Syntetické sdělení",
        "patient",
        topic_ids=("nezadouci_ucinky/jine",),
    )
    result = analyze_message(event(), lambda _: [fact])
    assert result["unmapped_concepts"] == ["confusion"]
    assert result["question_candidates"][0]["question"]["question_id"] == "jine"


def test_budget_keeps_all_recognized_topics_pending():
    topics = [
        "nezadouci_ucinky/bol_hlava",
        "nezadouci_ucinky/kuze",
        "psychoonkologicky_screening/deti",
        "bolest_analgeticka_terapie/sos",
    ]
    facts = [
        Fact(
            "reported_finding",
            "present",
            "Syntetické sdělení",
            "patient",
            topic_ids=(t,),
        )
        for t in topics
    ]
    extract = lambda *_: {
        "status": "unclear",
        "value": None,
        "source_index": None,
        "evidence": None,
        "follow_up": "Můžete doplnit podrobnosti?",
    }
    contact = MasterDialogue(lambda _: facts, extract, max_questions=1)
    packet = contact.start(event())
    assert packet["dialogue"]["state"] == "limited"
    assert set(packet["dialogue"]["pending_topic_ids"]) == set(topics)
    assert len(packet["facts"]) == len(topics)


def test_different_forms_keep_independent_question_ids_and_flow():
    topics = ["psychoonkologicky_screening/deti", "bolest_analgeticka_terapie/sos"]
    facts = [
        Fact(
            "reported_finding",
            "present",
            "Syntetické sdělení",
            "patient",
            topic_ids=(t,),
        )
        for t in topics
    ]

    def extract(question, *_):
        return {
            "status": "answered",
            "value": 0 if question.kind == "jedna" else 2,
            "source_index": 0,
            "evidence": "Syntetické sdělení",
            "follow_up": None,
        }

    contact = MasterDialogue(lambda _: facts, extract)
    contact.start(event())
    assert contact.active.question.id == "deti"
    contact.confirm()
    assert contact.active.question.id == "sos"
    result = contact.confirm()
    assert result["dialogue"]["state"] == "complete"
    assert len(result["question_answers"]) == 2


def test_regression_cases_cover_all_questions_and_are_not_prompt_examples():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    assert {t for c in cases for t in c["expected_topics"]} == set(TOPIC_IDS)
    assert len({c["id"] for c in cases}) == len(cases)
    payload = MasterExtractor(Client("synthetic-key")).payload(event())
    prompt = json.dumps(payload["messages"][:-1], ensure_ascii=False)
    assert all(case["text"] not in prompt for case in cases)


def test_evaluator_measures_model_ids_not_fallback_aliases():
    case = {
        "id": "fatigue",
        "text": "Jsem unavený.",
        "expected_topics": ["nezadouci_ucinky/unava"],
    }
    fact = Fact("fatigue", "present", case["text"], "patient")
    result = evaluate_case(case, lambda _: [fact])
    assert result["missing_topics"] == case["expected_topics"]
    assert not result["passed"]


def test_evaluator_separates_api_errors_from_recognition_errors():
    case = {
        "id": "test",
        "text": "Syntetické sdělení.",
        "expected_topics": [TOPIC_IDS[0]],
    }

    def unavailable(_):
        raise APIError("LLM API: HTTP 429.")

    error = evaluate_case(case, unavailable)
    success = {"expected_topics": [TOPIC_IDS[0]], "missing_topics": [], "passed": True}
    result = summarize([error, success])
    assert error["error_type"] == "api"
    assert result["error_cases"] == 1
    assert result["evaluated_cases"] == 1
    assert result["topic_recall"] == 1
    assert result["passed"] == 1
    assert summarize([error])["topic_recall"] is None
