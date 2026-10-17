"""Omezený MASTER rozhovor nad stávajícím extraktorem a Intake; bez triáže."""

import argparse
import json
import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .client import APIError, Client
from .core import Intake, load_question
from .flow import QuestionnaireFlow
from .master import MasterExtractor, analyze_message
from .master_contract import MessageEvent
from .pipeline import build_pipeline_packet


class MasterDialogue:
    def __init__(
        self,
        extract_message: Callable,
        extract_answer: Callable,
        *,
        extract_with_events: Callable | None = None,
        max_questions: int = 6,
        max_clarifications: int = 2,
        bulk_confirmation: bool = False,
        follow_up_topic: str | None = None,
    ):
        if type(max_questions) is not int or max_questions < 1:
            raise ValueError("Rozpočet kontaktu musí být kladné celé číslo.")
        if type(max_clarifications) is not int or max_clarifications < 0:
            raise ValueError("Limit doptání musí být nezáporné celé číslo.")
        self._extract_message, self._extract_answer = extract_message, extract_answer
        self._extract_with_events = extract_with_events
        self._bulk_confirmation = bulk_confirmation
        self._confirmed = False
        self._follow_up = (
            load_question(*follow_up_topic.split("/", 1)) if follow_up_topic else None
        )
        self._max_questions, self._max_clarifications = (
            max_questions,
            max_clarifications,
        )
        self._messages: list[MessageEvent] = []
        self._analyses: list[dict] = []
        self._flows: dict[str, QuestionnaireFlow] = {}
        self._sessions: list[Intake] = []
        self.active: Intake | None = None
        self.state = "needs_master_answer"
        self._questions_asked = 0
        self._reason: str | None = None
        self._pending_action: str | None = None

    def _checkpoint(self, checkpoint: Callable | None, action: str) -> bool:
        """Let the caller return to its UI before any targeted extraction."""
        if checkpoint is not None and checkpoint(self.snapshot()):
            self.state, self._reason = "paused", "external_checkpoint"
            self._pending_action = action
            return True
        return False

    def start(
        self, message: MessageEvent, *, checkpoint: Callable | None = None
    ) -> dict:
        if self._messages or self._flows:
            raise ValueError("Kontakt už byl zahájen.")
        self._messages.append(message)
        self._questions_asked = int(
            message.source in {"master_question", "targeted_answer"}
        )
        try:
            self._analyses.append(analyze_message(message, self._extract_message))
            if not self._checkpoint(checkpoint, "advance"):
                self._advance()
        except (APIError, ValueError, TypeError):
            # I při blokaci první zprávy musí zůstat zdroj k dalšímu zpracování.
            self.cancel("processing_error")
            raise
        return self.snapshot()

    def _refresh_targets(self):
        grouped: dict[str, set[str]] = {}
        if self._follow_up:
            grouped[self._follow_up.questionnaire_id] = {self._follow_up.id}
        for analysis in self._analyses:
            for candidate in analysis["question_candidates"]:
                q = candidate["question"]
                grouped.setdefault(q["questionnaire_id"], set()).add(q["question_id"])
        for form, targets in grouped.items():
            if form in self._flows:
                self._flows[form].add_targets(targets)
            else:
                self._flows[form] = QuestionnaireFlow(
                    form,
                    targets=targets,
                    allow_drafts=self._bulk_confirmation,
                )

    def _reserve_question(self):
        if self._questions_asked >= self._max_questions:
            self.state, self._reason = "limited", "question_budget"
        else:
            self._questions_asked += 1

    def _advance(self):
        self._refresh_targets()
        for flow in self._flows.values():
            while question := flow.next_question():
                session = Intake(
                    question,
                    self._extract_answer,
                    max_clarifications=self._max_clarifications,
                    extract_with_events=self._extract_with_events,
                )
                self.active = session
                if (
                    not self._bulk_confirmation
                    and self._questions_asked >= self._max_questions
                ):
                    self.state, self._reason = "limited", "question_budget"
                    return
                related = [
                    message
                    for message, analysis in zip(
                        self._messages, self._analyses, strict=True
                    )
                    if (
                        self._follow_up == question
                        and message.question == question.text
                    )
                    or any(
                        (
                            c["question"]["questionnaire_id"],
                            c["question"]["question_id"],
                        )
                        == (question.questionnaire_id, question.id)
                        for c in analysis["question_candidates"]
                    )
                    and (
                        (question.questionnaire_id, question.id)
                        != ("nezadouci_ucinky", "pocit")
                        or any(
                            fact["concept"] == "overall_feeling"
                            and type(fact.get("value")) is int
                            and 1 <= fact["value"] <= 5
                            and fact["subject"] == "patient"
                            and fact["presence"] == "present"
                            for fact in analysis["facts"]
                        )
                    )
                ]
                if related:
                    session.seed(related)
                if session.state == "unresolved" or (
                    self._bulk_confirmation and session.state == "needs_confirmation"
                ):
                    flow.record(session)
                    self._sessions.append(session)
                    self.active = None
                    continue
                self.state = session.state
                if self.state in {"needs_answer", "needs_confirmation"}:
                    self._reserve_question()
                return
        self.active = None
        incomplete = any(
            flow.snapshot()["state"] != "complete" for flow in self._flows.values()
        )
        uncovered = any(
            a["unmapped_concepts"] or a["unknown_subject_fact_indices"]
            for a in self._analyses
        )
        answered_follow_up = self._follow_up is not None and any(
            s.question == self._follow_up
            and s.state in {"confirmed", "needs_confirmation"}
            for s in self._sessions
        )
        no_facts = (
            not any(a["facts"] for a in self._analyses) and not answered_follow_up
        )
        self.state = "unresolved" if incomplete or uncovered or no_facts else "complete"
        self._reason = "open_findings" if self.state == "unresolved" else None

    def _validate_event(self, message: MessageEvent) -> None:
        patient_id = self._messages[0].patient_id
        if message.patient_id != patient_id or any(
            m.id == message.id for m in self._messages
        ):
            raise ValueError("Událost musí patřit stejnému pacientovi a mít nové ID.")
        if self._messages and datetime.fromisoformat(
            message.available_at
        ) < datetime.fromisoformat(self._messages[-1].available_at):
            raise ValueError("Událost nesmí předcházet poslední dostupné zprávě.")

    def submit(
        self, message: MessageEvent, *, checkpoint: Callable | None = None
    ) -> dict:
        if (
            self.state not in {"needs_answer", "needs_correction"}
            or self.active is None
        ):
            raise ValueError("Kontakt nyní nečeká na slovní odpověď.")
        self._validate_event(message)
        if message.question != self.active.next_question:
            raise ValueError("Událost neodpovídá skutečně položené otázce.")
        analysis = analyze_message(message, self._extract_message)
        self._messages.append(message)
        self._analyses.append(analysis)
        try:
            if self._checkpoint(checkpoint, "answer"):
                return self.snapshot()
            self.active.submit_event(message)
        except (APIError, ValueError, TypeError):
            # Ordinary failed extraction remains atomic; the caller may retain
            # an independently emitted alert and the original source receipt.
            self._messages.pop()
            self._analyses.pop()
            raise
        self._after_answer()
        return self.snapshot()

    def _after_answer(self):
        self.state = self.active.state
        if self.state == "unresolved" or (
            self._bulk_confirmation and self.state == "needs_confirmation"
        ):
            self._finish_active()
        elif self.state in {"needs_answer", "needs_confirmation"}:
            self._reserve_question()

    def resume(self) -> dict:
        """Continue a caller-requested pause without repeating general extraction.

        The checkpoint callable is never stored on the dialogue. This is an
        in-memory continuation, not durable dialogue recovery.
        """
        if self.state != "paused" or self._pending_action is None:
            raise ValueError("Rozhovor nyní nečeká na pokračování.")
        action = self._pending_action
        if action == "advance":
            self._advance()
        else:
            self.active.submit_event(self._messages[-1])
            self._after_answer()
        self._pending_action = None
        return self.snapshot()

    def _finish_active(self):
        session = self.active
        self._flows[session.question.questionnaire_id].record(session)
        self._sessions.append(session)
        self.active = None
        # Nová témata přidáváme až po záznamu aktivní relace; nemohou jí
        # změnit pořadí uprostřed potvrzování.
        self._advance()

    def confirm(self) -> dict:
        if self._bulk_confirmation:
            raise ValueError("Potvrďte celý souhrn odpovědí.")
        if self.state != "needs_confirmation" or self.active is None:
            raise ValueError("Není co potvrdit.")
        self.active.confirm()
        self._finish_active()
        return self.snapshot()

    def reject(self) -> dict:
        if self.state != "needs_confirmation" or self.active is None:
            raise ValueError("Není co odmítnout.")
        self.active.reject()
        self.state = self.active.state
        self._reserve_question()
        return self.snapshot()

    @property
    def review_sessions(self) -> tuple[Intake, ...]:
        return (*self._sessions, *([self.active] if self.active else []))

    def revise(self, index: int) -> dict:
        if (
            not self._bulk_confirmation
            or self._confirmed
            or self.state not in {"complete", "unresolved"}
            or type(index) is not int
            or not 0 <= index < len(self._sessions)
        ):
            raise ValueError("Tuto odpověď nyní nelze opravit.")
        selected = self._sessions[index]
        selected.revise()
        form = selected.question.questionnaire_id
        removed = self._flows[form].discard(selected.question.id)
        self._sessions = [
            session
            for session in self._sessions
            if not (
                session.question.questionnaire_id == form
                and session.question.id in removed
            )
        ]
        self.active = selected
        self.state, self._reason = selected.state, None
        self._reserve_question()
        return self.snapshot()

    def confirm_all(self) -> dict:
        if (
            not self._bulk_confirmation
            or self._confirmed
            or self.state not in {"complete", "unresolved", "limited"}
        ):
            raise ValueError("Nejprve dokončete všechny otázky.")
        for session in self.review_sessions:
            if session.state == "needs_confirmation":
                session.confirm()
        self._confirmed = True
        return self.snapshot()

    def cancel(self, reason="user_exit"):
        self.state, self._reason = "cancelled", reason

    def snapshot(self) -> dict:
        if not self._messages:
            raise ValueError("Kontakt zatím nemá úvodní zprávu.")
        sessions = [*self._sessions, *([self.active] if self.active else [])]
        packet = build_pipeline_packet(self._messages[0], [], sessions)
        facts, candidates, unmapped, unknown = [], {}, [], []
        for analysis in self._analyses:
            offset = len(facts)
            facts.extend(deepcopy(analysis["facts"]))
            unknown.extend(offset + i for i in analysis["unknown_subject_fact_indices"])
            for concept in analysis["unmapped_concepts"]:
                if concept not in unmapped:
                    unmapped.append(concept)
            for candidate in analysis["question_candidates"]:
                q = candidate["question"]
                ref = (q["questionnaire_id"], q["question_id"])
                entry = candidates.setdefault(ref, {"question": q, "fact_indices": []})
                entry["fact_indices"].extend(
                    offset + i for i in candidate["fact_indices"]
                )
        return {
            **packet,
            "facts": facts,
            "analysis_status": "processing_error"
            if self._reason == "processing_error"
            else "extracted"
            if facts
            else "no_facts",
            "messages": [asdict(m) for m in self._messages],
            "question_candidates": deepcopy(
                sorted(
                    candidates.values(),
                    key=lambda c: (
                        c["question"]["questionnaire_id"],
                        c["question"]["order"],
                    ),
                )
            ),
            "unmapped_concepts": unmapped,
            "unknown_subject_fact_indices": unknown,
            "dialogue": {
                "state": self.state,
                "reason": self._reason,
                "questions_asked": self._questions_asked,
                "max_questions": self._max_questions,
                "mode": "targeted_from_message",
                "pending_topic_ids": [
                    f"{form}/{q['question_id']}"
                    for form, flow in self._flows.items()
                    for q in flow.snapshot()["questions"]
                    if q["state"] in {"ready", "blocked"}
                ],
                "flows": [
                    {k: v for k, v in flow.snapshot().items() if k != "answers"}
                    for flow in self._flows.values()
                ],
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MEDDI: interaktivní MASTER QUESTION a cílené doptávání"
    )
    parser.add_argument(
        "--input", type=Path, help="Volitelná úvodní zpráva JSON místo prvního dotazu"
    )
    parser.add_argument(
        "--at",
        default="2026-10-16T10:00:00+02:00",
        help="Simulovaný čas dostupnosti zpráv",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=6,
        help="Celkový limit včetně MASTER, potvrzení a oprav (výchozí 6)",
    )
    parser.add_argument(
        "--max-clarifications",
        type=int,
        default=2,
        help="Limit doplňujících otázek na parametr (výchozí 2)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Vypsat konečný interní JSON"
    )
    parser.add_argument(
        "--output", type=Path, help="Uložit konečný nebo přerušený JSON"
    )
    args = parser.parse_args()
    contact = None
    code = 0
    try:
        client = Client.from_env()
        contact = MasterDialogue(
            MasterExtractor(client),
            client,
            extract_with_events=client.extract_events,
            max_questions=args.max_questions,
            max_clarifications=args.max_clarifications,
        )
        print(
            "Testujte se syntetickými odpověďmi. /konec ukončí kontakt, /moznosti nabídne odpovědi."
        )
        if args.input:
            message = MessageEvent(
                **json.loads(args.input.read_text(encoding="utf-8-sig"))
            )
        else:
            question = "Jak se dnes cítíte?"
            print(question)
            text = input("Vaše odpověď: ")
            if text.strip().casefold() == "/konec":
                return 0
            message = MessageEvent(
                "synthetic-master-01",
                "synthetic-patient",
                text,
                args.at,
                "master_question",
                "patient",
                question,
            )
        contact.start(message)
        while contact.state in {
            "needs_answer",
            "needs_correction",
            "needs_confirmation",
        }:
            if contact.state == "needs_confirmation":
                print(contact.active.patient_summary())
                text = input("Je to správně? [ano/ne nebo /konec]: ").strip().casefold()
                if text in {"ano", "a"}:
                    contact.confirm()
                elif text in {"ne", "n"}:
                    contact.reject()
                elif text == "/konec":
                    contact.cancel()
                elif text == "/moznosti":
                    print(
                        contact.active.question.patient_options()
                        or "Tato otázka nemá nabídku odpovědí."
                    )
                else:
                    print("Prosím odpovězte ano nebo ne.")
            else:
                question = contact.active.next_question
                print(question)
                text = input("Vaše odpověď: ")
                if text.strip().casefold() == "/konec":
                    contact.cancel()
                elif text.strip().casefold() == "/moznosti":
                    print(
                        contact.active.question.patient_options()
                        or "Tato otázka nemá nabídku odpovědí."
                    )
                else:
                    origin = contact._messages[0]
                    contact.submit(
                        MessageEvent(
                            f"{origin.id}-reply-{len(contact._messages)}",
                            origin.patient_id,
                            text,
                            message.available_at,
                            "targeted_answer",
                            origin.author,
                            question,
                        )
                    )
        print(
            {
                "complete": "Kontakt byl dokončen. Vybrané odpovědi jsou zaznamenané.",
                "limited": "Dosáhli jsme limitu dotazů. Nevyřešené údaje zůstávají zaznamenané.",
                "unresolved": "Část údajů zůstává nevyřešená nebo nemá přiřazenou otázku.",
                "cancelled": "Kontakt byl přerušen.",
            }[contact.state]
        )
        code = 0 if contact.state == "complete" else 2
    except (EOFError, KeyboardInterrupt):
        if contact and contact._messages:
            contact.cancel()
        print("\nKontakt byl přerušen.")
        code = 2
    except (APIError, ValueError, TypeError, OSError) as exc:
        if contact and contact._messages:
            contact.cancel("processing_error")
        print(f"Chyba: {exc}", file=sys.stderr)
        code = 1
    if contact and contact._messages:
        output = json.dumps(
            contact.snapshot(), ensure_ascii=False, indent=2, allow_nan=False
        )
        if args.debug:
            print(output)
        if args.output:
            try:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(output + "\n", encoding="utf-8")
            except OSError as exc:
                print(f"Nelze uložit výstup: {exc}", file=sys.stderr)
                return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
