"""První datový kontrakt zprávy a faktů; bez LLM volání, triáže a karty."""

import math
from dataclasses import asdict, dataclass
from datetime import datetime


def _number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


@dataclass(frozen=True)
class NumericRange:
    lower: int | float | None
    upper: int | float | None
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    def __post_init__(self):
        if self.lower is None and self.upper is None:
            raise ValueError("Rozsah potřebuje alespoň jednu mez.")
        if any(v is not None and not _number(v) for v in (self.lower, self.upper)):
            raise ValueError("Meze musí být konečná čísla nebo null.")
        if (
            type(self.lower_inclusive) is not bool
            or type(self.upper_inclusive) is not bool
        ):
            raise ValueError("Uzavřenost mezí musí být boolean.")
        if (
            self.lower is not None
            and self.upper is not None
            and (
                self.lower > self.upper
                or (
                    self.lower == self.upper
                    and not (self.lower_inclusive and self.upper_inclusive)
                )
            )
        ):
            raise ValueError("Prázdný nebo obrácený rozsah.")


@dataclass(frozen=True)
class MessageEvent:
    id: str
    patient_id: str
    text: str
    available_at: str
    source: str
    author: str
    question: str | None = None

    def __post_init__(self):
        if any(
            not isinstance(v, str) or not v.strip()
            for v in (self.id, self.patient_id, self.text)
        ):
            raise ValueError("Zpráva potřebuje ID, pacienta a neprázdný text.")
        timestamp = datetime.fromisoformat(self.available_at)
        if timestamp.utcoffset() is None:
            raise ValueError("Čas dostupnosti musí obsahovat časové pásmo.")
        if self.source not in {"master_question", "patient_message", "targeted_answer"}:
            raise ValueError("Neznámý zdroj zprávy.")
        if self.author not in {"patient", "caregiver", "team", "unknown"}:
            raise ValueError("Neznámý autor zprávy.")
        if self.source != "patient_message" and (
            not isinstance(self.question, str) or not self.question.strip()
        ):
            raise ValueError("Odpověď musí zachovat skutečně položenou otázku.")


@dataclass(frozen=True)
class Fact:
    concept: str
    presence: str
    evidence: str
    subject: str
    value: int | float | str | NumericRange | None = None
    unit: str | None = None
    time_text: str | None = None
    certainty: str = "stated"
    topic_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            not isinstance(self.topic_ids, tuple)
            or not all(isinstance(v, str) and v for v in self.topic_ids)
            or len(set(self.topic_ids)) != len(self.topic_ids)
        ):
            raise ValueError(
                "Témata faktu musí být jednoznačná neprázdná ID bez duplicit."
            )
        if not isinstance(self.concept, str) or not self.concept.strip():
            raise ValueError("Fakt potřebuje pojmenovaný pojem.")
        if self.presence not in {"present", "absent", "uncertain"}:
            raise ValueError("Neplatné rozlišení přítomnosti příznaku.")
        if self.subject not in {"patient", "caregiver", "unknown"}:
            raise ValueError("Fakt musí rozlišit, koho popisuje.")
        if self.certainty not in {"stated", "approximate", "uncertain"}:
            raise ValueError("Neplatná přesnost sdělení.")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("Fakt potřebuje doslovnou citaci.")
        if self.value is not None and not (
            _number(self.value) or isinstance(self.value, (str, NumericRange))
        ):
            raise ValueError("Hodnota musí být číslo, text, rozsah nebo null.")
        if self.presence == "absent" and self.value is not None:
            raise ValueError("Popřený příznak nemá domyšlenou měřenou hodnotu.")
        for text in (self.unit, self.time_text):
            if text is not None and (not isinstance(text, str) or not text.strip()):
                raise ValueError(
                    "Jednotka a časový text musí být neprázdný text nebo null."
                )

    @classmethod
    def from_dict(cls, data: dict):
        data = data.copy()
        if "topic_ids" in data:
            if not isinstance(data["topic_ids"], (list, tuple)):
                raise ValueError("topic_ids musí být seznam ID.")
            data["topic_ids"] = tuple(data["topic_ids"])
        if isinstance(data.get("value"), dict):
            data["value"] = NumericRange(**data["value"])
        return cls(**data)


def build_packet(message: MessageEvent, facts: list[Fact]) -> dict:
    """Aplikace připojí zdroj a stav; extraktor je nemůže sám potvrdit.

    Kontrola citace není důkaz správného významu ani úplnosti extrakce.
    Neznámé koncepty zůstávají v paketu pro další zpracování.
    """
    result = []
    for fact in facts:
        if fact.evidence not in message.text:
            raise ValueError("Citace faktu není v původní zprávě.")
        if fact.time_text is not None and fact.time_text not in message.text:
            raise ValueError("Časový text musí zachovat původní časové vyjádření.")
        result.append(
            {
                **asdict(fact),
                "topic_ids": list(fact.topic_ids),
                "source_message_id": message.id,
                "confirmation": "unconfirmed",
            }
        )
    return {"schema_version": 1, "message": asdict(message), "facts": result}
