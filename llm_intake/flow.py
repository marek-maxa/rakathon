"""Pořadí a větvení z definic. Bez LLM výběru témat, časovače a triáže."""

from collections.abc import Iterable
from pathlib import Path

from .core import DEFINITIONS, Intake, Question, find_question, load_questions


def parse_condition(condition: str) -> tuple[str, int]:
    """Jediný formát v podkladech je question_id:index; neprovádíme eval."""
    parent, index = condition.split(":")
    return parent, int(index)


class QuestionnaireFlow:
    """Celý formulář nebo vybrané vstupní otázky s podřízenými větvemi.

    Při cíleném vstupu nemusíme nejprve odpovídat na rodiče mimo zvolený
    rozsah. Jejich odpovědi nedoplňujeme. Uvnitř rozsahu platí podmínky normálně.
    """

    @classmethod
    def for_targets(
        cls,
        targets: Iterable[str],
        questionnaire_id: str | None = None,
        *,
        path: Path = DEFINITIONS,
    ) -> "QuestionnaireFlow":
        """Vytvoří QuestionnaireFlow pro cílené otázky s automatickým dohledáním dotazníku."""
        if isinstance(targets, str):
            raise TypeError("targets je seznam ID, nikoli jedno textové ID.")
        target_list = list(targets)
        if not target_list:
            raise ValueError("Cílený vstup potřebuje existující ID otázek.")
        if questionnaire_id is None:
            first = find_question(target_list[0], path=path)
            questionnaire_id = first.questionnaire_id
        return cls(questionnaire_id, targets=target_list, path=path)

    def __init__(
        self,
        questionnaire_id: str,
        *,
        targets: Iterable[str] | None = None,
        path: Path = DEFINITIONS,
    ):
        self.questionnaire_id = questionnaire_id
        self._questions = {
            q.id: q
            for q in load_questions(path)
            if q.questionnaire_id == questionnaire_id
        }
        if not self._questions:
            raise ValueError(f"Neznámý dotazník: {questionnaire_id}")
        if isinstance(targets, str):
            raise TypeError("targets je seznam ID, nikoli jedno textové ID.")
        self._targets = None if targets is None else set(targets)
        if self._targets is not None and (
            not self._targets or not self._targets <= self._questions.keys()
        ):
            raise ValueError("Cílený vstup potřebuje existující ID otázek.")
        self._sessions: dict[str, Intake] = {}
        self._selected = (
            set(self._questions) if self._targets is None else self._targets.copy()
        )
        for question in self._questions.values():
            if not question.condition:
                continue
            parent_id, index = parse_condition(question.condition)
            parent = self._questions.get(parent_id)
            if (
                parent is None
                or parent.order >= question.order
                or parent.kind not in {"jedna", "vice"}
                or not 0 <= index < len(parent.options)
            ):
                raise ValueError(f"Neplatná podmínka otázky: {question.id}")
            if parent_id in self._selected:
                self._selected.add(question.id)

    @property
    def sessions(self) -> tuple[Intake, ...]:
        """Ukončené relace v pořadí skutečného zpracování."""
        return tuple(self._sessions.values())

    def _eligible(self, question: Question) -> bool | None:
        if not question.condition:
            return True
        parent_id, index = parse_condition(question.condition)
        parent = self._questions[parent_id]
        if self._eligible(parent) is False:
            return False
        if parent_id in self._sessions:
            session = self._sessions[parent_id]
            if session.state != "confirmed":
                return None
            value = session.confirmed_data()["odpoved_index"]
            return index in value if parent.kind == "vice" else index == value
        if (
            self._targets is not None
            and question.id in self._targets
            and parent_id not in self._selected
        ):
            return True
        return None

    def next_question(self) -> Question | None:
        for question in self._questions.values():
            if (
                question.id in self._selected
                and question.id not in self._sessions
                and self._eligible(question) is True
            ):
                return question
        return None

    def record(self, session: Intake) -> None:
        """Přijímá jen očekávanou ukončenou relaci; návrh větev neaktivuje."""
        if session.question != self.next_question():
            raise ValueError("Relace neodpovídá další otázce tohoto průchodu.")
        if session.state not in {"confirmed", "unresolved"}:
            raise ValueError("Nejprve odpověď potvrďte nebo uzavřete jako nevyřešenou.")
        self._sessions[session.question.id] = session

    def snapshot(self) -> dict:
        questions = []
        for question in self._questions.values():
            if question.id not in self._selected:
                continue
            if question.id in self._sessions:
                state = self._sessions[question.id].state
            else:
                eligible = self._eligible(question)
                if eligible is True:
                    state = "ready"
                elif eligible is False:
                    state = "skipped"
                else:
                    state = "blocked"
            questions.append({"question_id": question.id, "state": state})
        states = {q["state"] for q in questions}
        if "ready" in states:
            state = "ready"
        elif "blocked" in states:
            state = "blocked"
        elif "unresolved" in states:
            state = "unresolved"
        else:
            state = "complete"
        return {
            "questionnaire_id": self.questionnaire_id,
            "mode": "questionnaire" if self._targets is None else "targeted",
            "targets": None
            if self._targets is None
            else [q for q in self._questions if q in self._targets],
            "state": state,
            "questions": questions,
            "answers": [session.snapshot() for session in self.sessions],
        }
