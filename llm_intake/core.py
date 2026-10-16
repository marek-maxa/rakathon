"""Validace a potvrzování jsou nezávislé na poskytovateli LLM."""

import json
import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

DEFINITIONS = (
    Path(__file__).resolve().parents[1]
    / "rakathon_meddi_onco_data/docs/dotazniky_definice.json"
)


@dataclass(frozen=True)
class Question:
    questionnaire_id: str
    id: str
    text: str
    kind: str
    options: tuple[str, ...] = ()
    instruction: str | None = None
    note: str | None = None
    option_colors: tuple[str | None, ...] = ()

    def specification(self) -> dict:
        return {
            "questionnaire_id": self.questionnaire_id,
            "question_id": self.id,
            "text": self.text,
            "type": self.kind,
            "instruction": self.instruction,
            "note": self.note,
            "options": [
                {"index": i, "text": text} for i, text in enumerate(self.options)
            ],
        }

    def schema(self) -> dict:
        if self.kind == "jedna":
            value = {"type": "integer", "enum": list(range(len(self.options)))}
        elif self.kind == "vice":
            value = {
                "type": "array",
                "items": {"type": "integer", "enum": list(range(len(self.options)))},
            }
        elif self.kind == "skala_1_10":
            value = {"type": "integer", "minimum": 1, "maximum": 10}
        elif self.kind == "cislo":
            value = {"type": "number", "minimum": 0}
        elif self.kind == "text":
            value = {"type": "string"}
        else:
            raise ValueError(f"Nepodporovaný typ otázky: {self.kind}")
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["answered", "unclear"]},
                "value": {"anyOf": [value, {"type": "null"}]},
                "source_index": {"type": ["integer", "null"]},
                "evidence": {"type": ["string", "null"]},
                "follow_up": {"type": ["string", "null"]},
            },
            "required": ["status", "value", "source_index", "evidence", "follow_up"],
        }


def load_question(
    questionnaire_id: str, question_id: str, path: Path = DEFINITIONS
) -> Question:
    for form in json.loads(path.read_text(encoding="utf-8")):
        if form["id"] != questionnaire_id:
            continue
        for q in form["otazky"]:
            if q["id"] == question_id:
                return Question(
                    questionnaire_id,
                    q["id"],
                    q["text"],
                    q["typ"],
                    tuple(o["text"] for o in q.get("moznosti", [])),
                    q.get("navod"),
                    q.get("poznamka"),
                    tuple(o.get("barva") for o in q.get("moznosti", [])),
                )
    raise ValueError(f"Neznámá otázka: {questionnaire_id}/{question_id}")


def validate(question: Question, result: dict, sources: list[str]) -> dict:
    """Ověří tvar, doménu hodnot a doslovnou citaci, nikoli správnost významu."""
    keys = {"status", "value", "source_index", "evidence", "follow_up"}
    if not isinstance(result, dict) or set(result) != keys:
        raise ValueError("LLM vrátilo neplatná pole extrakce.")
    value, status = result["value"], result["status"]
    if status == "unclear":
        if any(result[k] is not None for k in ("value", "source_index", "evidence")):
            raise ValueError("Nejasná odpověď musí mít hodnotu i zdroj null.")
        follow_up = result["follow_up"]
        if not (
            isinstance(follow_up, str)
            and 0 < len(follow_up.strip()) <= 240
            and follow_up.strip().endswith("?")
            and follow_up.count("?") == 1
            and "\n" not in follow_up
        ):
            raise ValueError(
                "Nejasná odpověď vyžaduje jednu krátkou doplňující otázku."
            )
        return deepcopy(result)
    if status != "answered":
        raise ValueError("Neplatný stav extrakce.")
    if result["follow_up"] is not None:
        raise ValueError("Přiřazená odpověď už nevyžaduje doptání, pouze potvrzení.")
    kind = question.kind
    if kind == "jedna":
        valid = type(value) is int and 0 <= value < len(question.options)
    elif kind == "vice":
        valid = isinstance(value, list) and all(
            type(v) is int and 0 <= v < len(question.options) for v in value
        )
        valid = valid and len(value) == len(set(value))
    elif kind == "skala_1_10":
        valid = type(value) is int and 1 <= value <= 10
    elif kind == "cislo":
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    elif kind == "text":
        valid = isinstance(value, str) and bool(value.strip())
    else:
        valid = False
    if not valid:
        raise ValueError("Extrahovaná hodnota neodpovídá typu nebo možnostem otázky.")
    index, evidence = result["source_index"], result["evidence"]
    if not (
        type(index) is int
        and 0 <= index < len(sources)
        and isinstance(evidence, str)
        and evidence.strip()
        and evidence in sources[index]
    ):
        raise ValueError("Chybí platná doslovná citace zdrojové odpovědi.")
    return deepcopy(result)


class Intake:
    """Jedna otázka: odpověď → návrh → potvrzení / odmítnutí → oprava.

    extract(question, sources, source_questions) vrací JSON podle question.schema().
    Stav zůstává při chybě modelu nebo validace nezměněný.
    """

    def __init__(
        self, question: Question, extract: Callable, *, max_clarifications: int = 2
    ):
        if type(max_clarifications) is not int or max_clarifications < 0:
            raise ValueError("Limit doptání musí být nezáporné celé číslo.")
        self.question = question
        self._extract = extract
        self._sources: list[str] = []
        self._draft: dict | None = None
        self._state = "needs_answer"
        self._revision = 0
        self._source_questions: list[str] = []
        self._clarifications = 0
        self._rejections = 0
        self._max_clarifications = max_clarifications
        self._unresolved_reason: str | None = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def next_question(self) -> str:
        if self.state == "needs_correction":
            return "Co je v navržené odpovědi jinak?"
        if self.state != "needs_answer":
            raise ValueError("Relace nyní nečeká na textovou odpověď.")
        if self._draft and self._draft["status"] == "unclear":
            return self._draft["follow_up"]
        return self.question.text

    def submit(self, text: str) -> dict:
        if self.state not in {"needs_answer", "needs_correction"}:
            raise ValueError("Nejprve návrh potvrďte nebo odmítněte.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Odpověď nesmí být prázdná.")
        sources = [*self._sources, text]
        source_questions = [*self._source_questions, self.next_question]
        result = validate(
            self.question,
            self._extract(self.question, sources.copy(), source_questions.copy()),
            sources,
        )
        self._draft, self._sources = result, sources
        self._source_questions = source_questions
        self._revision += 1
        self._state = (
            "needs_confirmation" if result["status"] == "answered" else "needs_answer"
        )
        if result["status"] == "unclear":

            def normalized(text):
                return text.strip().casefold().rstrip(" .?!")

            if self._clarifications >= self._max_clarifications:
                self._state, self._unresolved_reason = (
                    "unresolved",
                    "clarification_limit",
                )
            elif any(
                normalized(result["follow_up"]) == normalized(q)
                for q in source_questions
            ):
                self._state, self._unresolved_reason = "unresolved", "repeated_question"
            else:
                self._clarifications += 1
        return self.snapshot()

    def reject(self) -> None:
        if self.state != "needs_confirmation":
            raise ValueError("Není co odmítnout.")
        self._state = "needs_correction"
        self._rejections += 1

    def snapshot(self) -> dict:
        value = self._draft["value"] if self._draft else None
        if value is not None and self.question.kind == "jedna":
            answer = self.question.options[value]
        elif value is not None and self.question.kind == "vice":
            answer = [self.question.options[v] for v in value]
        else:
            answer = value
        indices = (
            [value]
            if value is not None and self.question.kind == "jedna"
            else value
            if value is not None and self.question.kind == "vice"
            else []
        )
        return {
            "schema_version": 2,
            "dotaznik_id": self.question.questionnaire_id,
            "otazka_id": self.question.id,
            "otazka": self.question.text,
            "revision": self._revision,
            "state": self.state,
            "confirmed": self.state == "confirmed",
            "odpoved": answer,
            "odpoved_index": deepcopy(value)
            if self.question.kind in {"jedna", "vice"}
            else None,
            "extraction": deepcopy(self._draft),
            "source_messages": self._sources.copy(),
            "source_questions": self._source_questions.copy(),
            "follow_up": self.next_question if self.state == "needs_answer" else None,
            "unresolved_reason": self._unresolved_reason,
            "metrics": {
                "successful_extractions": self._revision,
                "clarifications_issued": self._clarifications,
                "rejections": self._rejections,
                "max_clarifications": self._max_clarifications,
            },
            "signaly_odpovedi": [
                {
                    "odpoved_index": i,
                    "barva": self.question.option_colors[i]
                    if i < len(self.question.option_colors)
                    else None,
                }
                for i in indices
            ],
        }

    def confirm(self) -> dict:
        if self.state != "needs_confirmation":
            raise ValueError("Potvrdit lze pouze platný aktuální návrh.")
        self._state = "confirmed"
        return self.confirmed_data()

    def confirmed_data(self) -> dict:
        if self.state != "confirmed":
            raise ValueError("Odpověď zatím pacient nepotvrdil.")
        return self.snapshot()

    def patient_summary(self) -> str:
        if self.state == "unresolved":
            return "Odpověď se nepodařilo spolehlivě přiřadit. Ponecháme ji zaznamenanou bez vybrané možnosti."
        if self._draft is None or self._draft["status"] != "answered":
            return self.next_question
        answer = self.snapshot()["odpoved"]
        if isinstance(answer, list):
            answer = "; ".join(answer) if answer else "Žádná z uvedených možností"
        return f"Otázka: {self.question.text}\nVaše odpověď: {answer}"
