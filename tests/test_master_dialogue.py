import json
from dataclasses import asdict, replace
from unittest.mock import Mock

import pytest

from llm_intake import Intake, load_question
from llm_intake.client import APIError, Client
from llm_intake.dialogue import MasterDialogue, main
from llm_intake.master_contract import Fact, MessageEvent
from llm_intake.pipeline import build_pipeline_packet


def event(
    text="Jsem unavený.",
    *,
    id="synthetic-master",
    question="Jak se dnes cítíte?",
    source="master_question",
):
    return MessageEvent(
        id,
        "synthetic-patient",
        text,
        "2026-10-16T10:00:00+02:00",
        source,
        "patient",
        question,
    )


def answered(value, text, index=0):
    return {
        "status": "answered",
        "value": value,
        "source_index": index,
        "evidence": text,
        "follow_up": None,
    }


def unclear(question="Pomůže odpočinek bez spánku?"):
    return {
        "status": "unclear",
        "value": None,
        "source_index": None,
        "evidence": None,
        "follow_up": question,
    }


def fatigue(message):
    return [Fact("fatigue", "present", message.text, "patient")]


def reply(contact, text):
    return event(
        text,
        id=f"synthetic-reply-{len(contact.snapshot()['messages'])}",
        question=contact.active.next_question,
        source="targeted_answer",
    )


def test_seed_reuses_master_answer_with_actual_question_and_source():
    message = event("Odpočinek mi pomůže.")
    extract = Mock(return_value=answered(0, message.text))
    session = Intake(load_question("nezadouci_ucinky", "unava"), extract)
    session.seed([message])
    assert session.state == "needs_confirmation"
    assert extract.call_args.args[2] == [message.question]
    assert session.snapshot()["source_questions"] == ["Jak se dnes cítíte?"]
    with pytest.raises(ValueError):
        session.seed([message])
    packet = build_pipeline_packet(message, [], [session])
    assert packet["question_answers"][0]["turns"][0]["source_message_id"] == message.id
    assert (
        packet["question_answers"][0]["turns"][0]["available_at"]
        == message.available_at
    )
    assert not packet["question_answers"][0]["confirmed"]


def test_spontaneous_seed_preserves_unknown_question_and_author_context():
    message = replace(
        event(), source="patient_message", question=None, author="caregiver"
    )
    client = Client("synthetic-key")
    payloads = []

    def extract(q, sources, questions, events):
        payloads.append(client.payload(q, sources, questions, events))
        return unclear()

    session = Intake(
        load_question("nezadouci_ucinky", "unava"),
        lambda *_: None,
        extract_with_events=extract,
    )
    session.seed([message])
    actual = json.loads(payloads[0]["messages"][-1]["content"])
    assert actual["source_questions"] == [None]
    assert actual["source_authors"] == ["caregiver"]
    assert "synthetic-patient" not in payloads[0]["messages"][-1]["content"]


def test_failed_seed_is_atomic():
    session = Intake(
        load_question("nezadouci_ucinky", "unava"), Mock(side_effect=APIError("fail"))
    )
    before = session.snapshot()
    with pytest.raises(APIError):
        session.seed([event()])
    assert session.snapshot() == before


def test_complete_master_value_goes_directly_to_confirmation():
    contact = MasterDialogue(
        fatigue, Mock(return_value=answered(0, "Odpočinek mi pomůže."))
    )
    packet = contact.start(event("Odpočinek mi pomůže."))
    assert contact.state == "needs_confirmation"
    assert packet["dialogue"]["questions_asked"] == 2
    packet = contact.confirm()
    assert contact.state == "complete"
    assert packet["question_answers"][0]["confirmed"] is True
    assert packet["facts"][0]["confirmation"] == "unconfirmed"


def test_missing_value_is_clarified_without_repeating_master():
    extract = Mock(side_effect=[unclear(), answered(0, "Ano, pomůže.", 1)])
    contact = MasterDialogue(fatigue, extract)
    contact.start(event())
    question = contact.active.next_question
    contact.submit(reply(contact, "Ano, pomůže."))
    result = contact.confirm()
    answer = result["question_answers"][0]
    assert [turn["question"] for turn in answer["turns"]] == [
        "Jak se dnes cítíte?",
        question,
    ]
    assert answer["evidence"]["turn_index"] == 1
    assert result["dialogue"]["questions_asked"] == 3
    assert len(result["messages"]) == 2
    assert result["facts"][1]["source_message_id"] == result["messages"][1]["id"]


def test_rejection_requires_correction_and_never_exports_old_value():
    extract = Mock(
        side_effect=[
            answered(0, "Jsem unavený."),
            answered(2, "Odpočinek nepomáhá, mytí nezvládám.", 1),
        ]
    )
    contact = MasterDialogue(fatigue, extract)
    contact.start(event())
    rejected = contact.reject()
    assert rejected["question_answers"][0]["value"] is None
    assert contact.state == "needs_correction"
    contact.submit(reply(contact, "Odpočinek nepomáhá, mytí nezvládám."))
    result = contact.confirm()
    assert result["question_answers"][0]["value"] == 2
    assert result["dialogue"]["questions_asked"] == 4


def test_global_budget_stops_before_issuing_another_question():
    extract = Mock(return_value=unclear())
    contact = MasterDialogue(fatigue, extract, max_questions=1)
    result = contact.start(event())
    assert contact.state == "limited"
    assert result["dialogue"]["reason"] == "question_budget"
    assert result["dialogue"]["questions_asked"] == 1
    assert result["question_answers"][0]["value"] is None
    extract.assert_not_called()
    with pytest.raises(ValueError):
        contact.confirm()


def test_correction_questions_also_consume_global_budget():
    extract = Mock(
        side_effect=[answered(0, "Jsem unavený."), answered(1, "Jen při sportu.", 1)]
    )
    contact = MasterDialogue(fatigue, extract, max_questions=4)
    contact.start(event())
    contact.reject()
    contact.submit(reply(contact, "Jen při sportu."))
    result = contact.reject()
    assert contact.state == "limited"
    assert result["dialogue"]["questions_asked"] == 4
    assert result["question_answers"][0]["value"] is None


def test_per_question_limit_remains_unresolved_without_guess():
    contact = MasterDialogue(
        fatigue,
        Mock(side_effect=[unclear(), unclear("Omezuje únava běžné aktivity?")]),
        max_clarifications=1,
    )
    contact.start(event())
    contact.submit(reply(contact, "Nevím."))
    assert contact.state == "unresolved"
    result = contact.snapshot()["question_answers"][0]
    assert result["unresolved_reason"] == "clarification_limit"
    assert result["value"] is None


def test_new_earlier_topic_does_not_interrupt_active_confirmation():
    new_text = "Odpočinek mi pomůže, ale dvakrát jsem zvracel."

    def facts(message):
        if message.text == new_text:
            return [
                Fact("fatigue", "present", "Odpočinek mi pomůže", "patient"),
                Fact(
                    "vomiting.episodes", "present", "dvakrát jsem zvracel", "patient", 2
                ),
            ]
        return fatigue(message)

    extract = Mock(
        side_effect=[
            unclear(),
            answered(0, "Odpočinek mi pomůže", 1),
            answered(0, "dvakrát jsem zvracel"),
        ]
    )
    contact = MasterDialogue(facts, extract)
    contact.start(event())
    contact.submit(reply(contact, new_text))
    assert contact.active.question.id == "unava"
    contact.confirm()
    assert contact.active.question.id == "zvraceni"
    result = contact.confirm()
    assert [a["question"]["question_id"] for a in result["question_answers"]] == [
        "unava",
        "zvraceni",
    ]
    assert len(result["messages"]) == 2
    assert contact.state == "complete"


def test_negative_confirmed_parent_skips_conditional_description():
    facts = lambda m: [
        Fact("bleeding", "uncertain", m.text, "patient", certainty="uncertain")
    ]
    extract = Mock(
        side_effect=[unclear("Vidíte krev nebo modřiny?"), answered(0, "Ne.", 1)]
    )
    contact = MasterDialogue(facts, extract)
    contact.start(event("Možná krvácím."))
    contact.submit(reply(contact, "Ne."))
    packet = contact.confirm()
    assert contact.state == "complete"
    assert extract.call_count == 2
    assert packet["dialogue"]["flows"][0]["questions"][-1]["state"] == "skipped"


def test_positive_parent_opens_child_and_reuses_existing_message():
    message = event("Krvácím z dásní, rychle to přestalo.")
    facts = lambda m: [Fact("bleeding", "present", m.text, "patient")]
    extract = Mock(
        side_effect=[answered(1, message.text), answered(message.text, message.text)]
    )
    contact = MasterDialogue(facts, extract)
    contact.start(message)
    contact.confirm()
    assert contact.active.question.id == "krvaceni_popis"
    packet = contact.confirm()
    assert contact.state == "complete"
    assert packet["dialogue"]["questions_asked"] == 3


def test_unmapped_findings_remain_open_after_confirmed_answer():
    facts = lambda m: [
        *fatigue(m),
        Fact("sleep_difficulty", "present", m.text, "patient"),
    ]
    contact = MasterDialogue(facts, Mock(return_value=answered(0, "Jsem unavený.")))
    contact.start(event())
    result = contact.confirm()
    assert contact.state == "unresolved"
    assert result["unmapped_concepts"] == ["sleep_difficulty"]
    assert result["question_answers"][0]["confirmed"] is True


@pytest.mark.parametrize("failure_stage", ["facts", "answer"])
def test_failed_followup_does_not_commit_message_or_answer(failure_stage):
    fact_extract = (
        Mock(side_effect=[fatigue(event()), APIError("fail")])
        if failure_stage == "facts"
        else fatigue
    )
    answer_extract = Mock(side_effect=[unclear(), APIError("fail")])
    contact = MasterDialogue(fact_extract, answer_extract)
    contact.start(event())
    before = contact.snapshot()
    with pytest.raises(APIError):
        contact.submit(reply(contact, "Pomůže."))
    assert contact.snapshot() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("patient_id", "other"),
        ("id", "synthetic-master"),
        ("available_at", "2026-10-15T10:00:00+02:00"),
        ("question", "Jiná otázka?"),
    ],
)
def test_wrong_source_or_chronology_is_rejected(field, value):
    contact = MasterDialogue(fatigue, Mock(return_value=unclear()))
    contact.start(event())
    with pytest.raises(ValueError):
        contact.submit(replace(reply(contact, "Ano."), **{field: value}))
    assert len(contact.snapshot()["messages"]) == 1


def test_snapshot_is_detached_and_contains_no_colors():
    contact = MasterDialogue(fatigue, Mock(return_value=answered(0, "Jsem unavený.")))
    contact.start(event())
    result = contact.snapshot()
    assert "barva" not in json.dumps(result)
    assert "signaly_odpovedi" not in json.dumps(result)
    result["question_candidates"][0]["question"]["options"].clear()
    assert contact.snapshot()["question_candidates"][0]["question"]["options"]


def test_cli_master_clarification_correction_and_file_export(
    monkeypatch, tmp_path, capsys
):
    from llm_intake.master import MasterExtractor

    output = tmp_path / "nested" / "contact.json"
    monkeypatch.setattr(Client, "from_env", lambda: Client("synthetic-key"))
    monkeypatch.setattr(
        MasterExtractor, "__call__", lambda _, message: fatigue(message)
    )
    extract = Mock(
        side_effect=[
            unclear(),
            answered(0, "Ano, pomůže.", 1),
            answered(2, "Ne, mytí nezvládám.", 2),
        ]
    )
    monkeypatch.setattr(Client, "extract_events", lambda *args: extract(*args))
    responses = iter(
        [
            "Jsem unavený.",
            "/moznosti",
            "Ano, pomůže.",
            "ne",
            "Ne, mytí nezvládám.",
            "ano",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    monkeypatch.setattr("sys.argv", ["dialogue", "--output", str(output), "--debug"])
    assert main() == 0
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["dialogue"]["state"] == "complete"
    assert packet["question_answers"][0]["value"] == 2
    assert packet["question_answers"][0]["confirmed"] is True
    assert len(packet["messages"]) == 3
    assert extract.call_count == 3
    assert "- Ano." in capsys.readouterr().out


def test_cli_cancel_keeps_unconfirmed_value(monkeypatch, tmp_path):
    from llm_intake.master import MasterExtractor

    output = tmp_path / "cancelled.json"
    monkeypatch.setattr(Client, "from_env", lambda: Client("synthetic-key"))
    monkeypatch.setattr(
        MasterExtractor, "__call__", lambda _, message: fatigue(message)
    )
    monkeypatch.setattr(
        Client, "extract_events", lambda *_: answered(0, "Jsem unavený.")
    )
    responses = iter(["Jsem unavený.", "/konec"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    monkeypatch.setattr("sys.argv", ["dialogue", "--output", str(output)])
    assert main() == 2
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["dialogue"]["state"] == "cancelled"
    assert packet["question_answers"][0]["confirmed"] is False


def test_exhausted_budget_does_not_pay_for_seed_that_cannot_be_confirmed():
    extract = Mock(return_value=answered(0, "Jsem unavený."))
    contact = MasterDialogue(fatigue, extract, max_questions=1)
    result = contact.start(event())
    assert contact.state == "limited"
    assert result["question_answers"][0]["value"] is None
    assert result["question_answers"][0]["confirmed"] is False
    extract.assert_not_called()
    with pytest.raises(ValueError):
        contact.confirm()


def test_cli_file_input_preserves_original_question_and_clock(
    monkeypatch, tmp_path, capsys
):
    from llm_intake.master import MasterExtractor

    initial = replace(
        event("Odpočinek mi pomůže."), source="patient_message", question=None
    )
    input_path, output_path = tmp_path / "input.json", tmp_path / "output.json"
    input_path.write_text(json.dumps(asdict(initial)), encoding="utf-8-sig")
    monkeypatch.setattr(Client, "from_env", lambda: Client("synthetic-key"))
    monkeypatch.setattr(
        MasterExtractor, "__call__", lambda _, message: fatigue(message)
    )
    monkeypatch.setattr(Client, "extract_events", lambda *_: answered(0, initial.text))
    monkeypatch.setattr("builtins.input", lambda _: "ano")
    monkeypatch.setattr(
        "sys.argv",
        ["dialogue", "--input", str(input_path), "--output", str(output_path)],
    )
    assert main() == 0
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert packet["question_answers"][0]["turns"][0]["question"] is None
    assert packet["messages"][0]["available_at"] == initial.available_at
    assert packet["dialogue"]["questions_asked"] == 1
    assert "Jak se dnes cítíte?" not in capsys.readouterr().out
