"""Otevřená zpráva → validované fakty a kandidáti otázek. Bez triáže."""

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .client import ASSETS, APIError, Client
from .master_contract import Fact, MessageEvent, build_packet
from .pipeline import build_pipeline_packet
from .question_catalog import TOPIC_QUESTIONS, load_catalog


def load_schema() -> dict:
    return json.loads((ASSETS / "master_schema.json").read_text(encoding="utf-8"))


def _model_message(message: MessageEvent) -> dict:
    return {
        "text": message.text,
        "question": message.question,
        "author": message.author,
    }


def validate_facts(result: dict, message: MessageEvent) -> list[Fact]:
    """API schéma doplňujeme kontrolou typů, rozsahů a doslovných zdrojů.

    Výsledek vznikne až po ověření celého seznamu. Ověřený tvar a citace
    nedokazují správnost významu ani úplnost extrakce.
    """
    if (
        not isinstance(result, dict)
        or set(result) != {"facts"}
        or not isinstance(result["facts"], list)
    ):
        raise ValueError("Neplatná struktura extrakce zprávy.")
    schema = load_schema()["properties"]["facts"]["items"]
    fields = set(schema["required"])
    range_fields = {"lower", "upper", "lower_inclusive", "upper_inclusive"}
    facts = []
    for item in result["facts"]:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Neplatná pole faktu.")
        if isinstance(item["value"], dict) and set(item["value"]) != range_fields:
            raise ValueError("Rozsah potřebuje obě meze a jejich uzavřenost.")
        if not isinstance(item["concept"], str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", item["concept"]
        ):
            raise ValueError(
                "Pojem musí být anglický identifikátor, případně s tečkou."
            )
        if isinstance(item["value"], str) and not item["value"].strip():
            raise ValueError("Textová hodnota nesmí být prázdná.")
        try:
            facts.append(Fact.from_dict(item))
        except (TypeError, ValueError) as exc:
            raise ValueError("Neplatná hodnota faktu.") from exc
    build_packet(message, facts)
    return facts


class MasterExtractor:
    """Tentýž API klient jako Intake, samostatný prompt a výstupní schéma."""

    def __init__(self, client: Client):
        self.client = client

    def payload(self, message: MessageEvent) -> dict:
        catalog = load_catalog()
        guide = {
            topic: [catalog[ref] for ref in refs]
            for topic, refs in TOPIC_QUESTIONS.items()
        }
        messages = [
            {
                "role": "system",
                "content": (ASSETS / "master_prompt.md").read_text(encoding="utf-8"),
            }
        ]
        examples = json.loads(
            (ASSETS / "master_examples.json").read_text(encoding="utf-8")
        )
        for example in examples:
            # Doplnění null a uzavřenosti rozsahů podle stejného kontraktu.
            facts = [asdict(Fact.from_dict(fact)) for fact in example["facts"]]
            validate_facts({"facts": facts}, MessageEvent(**example["message"]))
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "message": _model_message(
                                    MessageEvent(**example["message"])
                                )
                            },
                            ensure_ascii=False,
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps({"facts": facts}, ensure_ascii=False),
                    },
                ]
            )
        # ID pacienta a systémové časy extraktor k porozumění nepotřebuje.
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "message": _model_message(message),
                        "concept_guide": guide,
                    },
                    ensure_ascii=False,
                ),
            }
        )
        return self.client.structured_payload(
            messages, load_schema(), "patient_message_facts"
        )

    def __call__(self, message: MessageEvent) -> list[Fact]:
        return validate_facts(self.client.send(self.payload(message)), message)


def analyze_message(
    message: MessageEvent, extract: Callable[[MessageEvent], list[Fact]]
) -> dict:
    """Vrací kandidáty, ne hotový plán či pacientem potvrzené odpovědi.

    Popření a potíže pečujícího uchováme, ale samy nespouštějí dotaz pacientovi.
    Pojem mimo počáteční mapování se nesmí potichu ztratit.
    """
    facts = extract(message)
    catalog = load_catalog()
    reasons: dict[tuple[str, str], list[int]] = {}
    unmapped, unknown_subject = [], []
    for index, fact in enumerate(facts):
        topic = fact.concept.split(".", 1)[0]
        if topic not in TOPIC_QUESTIONS and fact.concept not in unmapped:
            unmapped.append(fact.concept)
        if fact.subject == "unknown":
            unknown_subject.append(index)
        if fact.subject != "patient" or fact.presence == "absent":
            continue
        for ref in TOPIC_QUESTIONS.get(topic, ()):
            reasons.setdefault(ref, []).append(index)
    return {
        **build_pipeline_packet(message, facts),
        "analysis_status": "extracted" if facts else "no_facts",
        "question_candidates": [
            {"question": package, "fact_indices": reasons[ref]}
            for ref, package in catalog.items()
            if ref in reasons
        ],
        "unmapped_concepts": unmapped,
        "unknown_subject_fact_indices": unknown_subject,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MEDDI: zpráva → fakta a kandidáti otázek (JSON)"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="JSON zprávy podle MessageEvent; použijte syntetická data",
    )
    args = parser.parse_args()
    try:
        message = MessageEvent(**json.loads(args.input.read_text(encoding="utf-8-sig")))
        packet = analyze_message(message, MasterExtractor(Client.from_env()))
        print(json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False))
    except (APIError, ValueError, TypeError, OSError) as exc:
        print(f"Chyba: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
