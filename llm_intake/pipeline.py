"""Jedna JSON obálka pro další pipeline, bez barev a rozhodnutí o triáži."""

from collections.abc import Iterable

from .core import Intake
from .master_contract import Fact, MessageEvent, build_packet


def build_pipeline_packet(
    message: MessageEvent, facts: list[Fact], sessions: Iterable[Intake] = ()
) -> dict:
    """Zpráva je podnět kontaktu; skutečné otázky/odpovědi zůstávají v turns.

    Nový typ paketu llm_intake / v1 nemění samostatný export Intake v2.
    Časy jednotlivých tahů dosavadní Intake nemá; zde je nevymýšlíme.
    """
    answers, seen = [], set()
    for session in sessions:
        question = session.question
        ref = (question.questionnaire_id, question.id)
        if ref in seen:
            raise ValueError("Jedna obálka nesmí obsahovat dvě relace stejné otázky.")
        seen.add(ref)
        snapshot = session.snapshot()
        current = session.state in {"needs_confirmation", "confirmed"}
        extraction = snapshot["extraction"] if current else None
        answers.append(
            {
                "question": question.specification(),
                "state": session.state,
                "confirmed": snapshot["confirmed"],
                "revision": snapshot["revision"],
                "value": extraction["value"] if extraction else None,
                "answer": snapshot["odpoved"] if current else None,
                "evidence": {
                    "turn_index": extraction["source_index"],
                    "text": extraction["evidence"],
                }
                if extraction
                else None,
                "turns": [
                    {
                        "question": q,
                        "answer": text,
                        **(
                            {
                                "source_message_id": event["id"],
                                "available_at": event["available_at"],
                                "author": event["author"],
                            }
                            if event
                            else {}
                        ),
                    }
                    for q, text, event in zip(
                        snapshot["source_questions"],
                        snapshot["source_messages"],
                        snapshot.get(
                            "source_events", [None] * len(snapshot["source_messages"])
                        ),
                        strict=True,
                    )
                ],
                "follow_up": snapshot["follow_up"],
                "unresolved_reason": snapshot["unresolved_reason"],
                "metrics": snapshot["metrics"],
            }
        )
    return {
        "kind": "llm_intake",
        **build_packet(message, facts),
        "question_answers": answers,
    }
