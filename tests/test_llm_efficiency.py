import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from llm_intake.client import APIError, Client
from llm_intake.core import load_questions
from llm_intake.dialogue import MasterDialogue, main
from llm_intake.evaluate_topics import evaluate_case, summarize
from llm_intake.master import MasterExtractor
from llm_intake.master_contract import Fact, MessageEvent
from llm_intake.question_catalog import load_topic_catalog


def event(text="Jsem unavený."):
    return MessageEvent(
        "synthetic",
        "synthetic",
        text,
        "2026-10-16T10:00:00+02:00",
        "master_question",
        "patient",
        "Jak se dnes cítíte?",
    )


def test_compact_catalogue_keeps_all_semantic_fields_and_reusable_prefix():
    extractor = MasterExtractor(Client("synthetic-key"))
    first = extractor.payload(event())
    second = extractor.payload(event("Dnes zvracím."))
    assert first["messages"][:-1] == second["messages"][:-1]
    context = json.loads(first["messages"][-1]["content"])
    full = load_topic_catalog()
    assert {r["topic_id"] for r in context["topic_catalog"]} == set(full)
    for row in context["topic_catalog"]:
        source = full[row["topic_id"]]["question"]
        for key in ("text", "type", "instruction", "note", "options"):
            assert row["question"].get(key) == source[key]
        if source["questionnaire_note"]:
            assert (
                context["questionnaire_context"][source["questionnaire_id"]]
                == source["questionnaire_note"]
            )
    # Proměnlivá zpráva je až za celým statickým katalogem v posledním vstupu.
    assert (
        first["messages"][-1]["content"].split(',"message":', 1)[0]
        == second["messages"][-1]["content"].split(',"message":', 1)[0]
    )


def test_targeted_examples_are_bounded_same_type_and_stable():
    client = Client("synthetic-key")
    questions = {(q.questionnaire_id, q.id): q for q in load_questions()}
    for question in questions.values():
        first = client.payload(question, ["Syntetická odpověď."])
        second = client.payload(question, ["Jiná odpověď."])
        assert first["messages"][:-1] == second["messages"][:-1]
        examples = first["messages"][1:-1:2]
        assert 1 <= len(examples) <= 3
        for example in examples:
            package = json.loads(example["content"])["question"]
            assert package["type"] == question.kind
            assert (
                package
                == questions[
                    (package["questionnaire_id"], package["question_id"])
                ].specification()
            )


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {
            "prompt_tokens": 123,
            "completion_tokens": 10,
            "total_tokens": 133,
            "prompt_tokens_details": {"cached_tokens": 100},
            "completion_tokens_details": {"reasoning_tokens": 2},
        },
    ],
)
def test_usage_observer_reports_counts_without_text_or_keys(monkeypatch, usage):
    opener = Mock()
    opener.open.return_value = BytesIO(
        json.dumps(
            {
                "usage": usage,
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            }
        ).encode()
    )
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    recorded = []
    client = Client("private-key", on_usage=recorded.append)
    client.send(
        client.structured_payload(
            [{"role": "user", "content": "private-text"}], {}, "test"
        )
    )
    assert len(recorded) == 1
    assert recorded[0]["prompt_tokens"] == (123 if usage else None)
    assert recorded[0]["cached_tokens"] == (100 if usage else None)
    assert recorded[0]["latency_ms"] >= 0
    assert "private-text" not in json.dumps(recorded)
    assert "private-key" not in json.dumps(recorded)


def test_precision_evaluator_rejects_extra_topic_despite_full_recall():
    case = {
        "id": "test",
        "text": "Jsem unavený.",
        "expected_topics": ["nezadouci_ucinky/unava"],
        "allowed_topics": ["nezadouci_ucinky/unava"],
    }
    result = evaluate_case(
        case,
        lambda _: [
            Fact(
                "fatigue",
                "present",
                case["text"],
                "patient",
                topic_ids=("nezadouci_ucinky/unava", "esas/unava"),
            )
        ],
    )
    assert result["missing_topics"] == []
    assert result["unexpected_topics"] == ["esas/unava"]
    assert not result["passed"]
    assert summarize([result])["topic_precision"] == 0.5


def test_evaluator_rejects_wrong_subject_or_negation_even_with_right_topic():
    case = {
        "id": "test",
        "text": "Nezvracím.",
        "expected_topics": ["nezadouci_ucinky/zvraceni"],
        "allowed_topics": ["nezadouci_ucinky/zvraceni"],
        "fact_checks": [
            {
                "topic_id": "nezadouci_ucinky/zvraceni",
                "presence": "absent",
                "subject": "patient",
            }
        ],
    }
    result = evaluate_case(
        case,
        lambda _: [
            Fact(
                "vomiting",
                "present",
                case["text"],
                "caregiver",
                topic_ids=("nezadouci_ucinky/zvraceni",),
            )
        ],
    )
    assert result["failed_fact_checks"]
    assert not result["passed"]


def test_confirming_last_allowed_question_does_not_extract_next_topic():
    message = event()
    facts = [
        Fact("reported_finding", "present", message.text, "patient", topic_ids=(topic,))
        for topic in ("nezadouci_ucinky/prujem", "nezadouci_ucinky/unava")
    ]
    extract = Mock(
        return_value={
            "status": "answered",
            "value": 0,
            "source_index": 0,
            "evidence": message.text,
            "follow_up": None,
        }
    )
    contact = MasterDialogue(lambda _: facts, extract, max_questions=2)
    contact.start(message)
    packet = contact.confirm()
    assert contact.state == "limited"
    assert extract.call_count == 1
    assert len(packet["facts"]) == 2
    assert packet["dialogue"]["pending_topic_ids"] == ["nezadouci_ucinky/unava"]


def test_provider_content_filter_is_reported_without_echoing_response(monkeypatch):
    opener = Mock()
    opener.open.side_effect = HTTPError(
        "https://example.invalid",
        400,
        "error",
        {},
        BytesIO(
            json.dumps(
                {"error": {"code": "content_filter", "message": "private-body"}}
            ).encode()
        ),
    )
    monkeypatch.setattr("llm_intake.client.request.build_opener", lambda *_: opener)
    client = Client("private-key")
    with pytest.raises(APIError, match="content_filter") as caught:
        client.send(client.structured_payload([], {}, "test"))
    assert "private-body" not in str(caught.value)
    assert "private-key" not in str(caught.value)


def test_failed_initial_analysis_preserves_unprocessed_message():
    message = event()
    contact = MasterDialogue(Mock(side_effect=APIError("content_filter")), Mock())
    with pytest.raises(APIError):
        contact.start(message)
    packet = contact.snapshot()
    assert packet["messages"][0]["text"] == message.text
    assert packet["analysis_status"] == "processing_error"
    assert packet["dialogue"]["reason"] == "processing_error"
    assert packet["dialogue"]["state"] == "cancelled"
    assert packet["facts"] == []


def test_cli_saves_initial_message_on_provider_failure(monkeypatch, tmp_path, capsys):
    path = tmp_path / "failed.json"
    monkeypatch.setattr(Client, "from_env", lambda: Client("synthetic-key"))
    monkeypatch.setattr(
        MasterExtractor, "__call__", Mock(side_effect=APIError("content_filter"))
    )
    monkeypatch.setattr("sys.argv", ["dialogue", "--output", str(path)])
    monkeypatch.setattr("builtins.input", lambda _: "Syntetické sdělení.")
    assert main() == 1
    packet = json.loads(path.read_text(encoding="utf-8"))
    assert packet["messages"][0]["text"] == "Syntetické sdělení."
    assert packet["analysis_status"] == "processing_error"
    assert "content_filter" in capsys.readouterr().err
