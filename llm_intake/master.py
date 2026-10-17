"""Otevřená zpráva → validované fakty a kandidáti otázek. Bez triáže."""

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .client import ASSETS, APIError, Client, compact_json
from .master_contract import Fact, MessageEvent, build_packet
from .pipeline import build_pipeline_packet
from .question_catalog import (
    load_catalog,
    load_topic_catalog,
    lookup_questions,
    resolve_topics,
)


def load_schema() -> dict:
    schema = json.loads((ASSETS / "master_schema.json").read_text(encoding="utf-8"))
    schema["properties"]["facts"]["items"]["properties"]["topic_ids"]["items"][
        "enum"
    ] = list(load_topic_catalog())
    return schema


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
    allowed_topics = set(schema["properties"]["topic_ids"]["items"]["enum"])
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
            fact = Fact.from_dict(item)
            if not set(fact.topic_ids) <= allowed_topics:
                raise ValueError("Neznámé ID tématu.")
            facts.append(fact)
        except (TypeError, ValueError) as exc:
            raise ValueError("Neplatná hodnota faktu.") from exc
    build_packet(message, facts)
    return facts


class MasterExtractor:
    """Tentýž API klient jako Intake, samostatný prompt a výstupní schéma."""

    def __init__(self, client: Client, clinical_fields=None):
        self.client = client
        self.clinical_fields = clinical_fields

    def payload(self, message: MessageEvent) -> dict:
        topics = load_topic_catalog()
        contexts = {}
        guide = []
        for row in topics.values():
            question = row["question"]
            if question["questionnaire_note"]:
                contexts[question["questionnaire_id"]] = question["questionnaire_note"]
            # Úplné texty a možnosti zůstávají. Pořadí, podmínky a duplicitní
            # ID vyhodnocuje kód; poznámka celého formuláře stačí jednou.
            semantic = {
                key: question[key]
                for key in ("text", "type", "instruction", "note", "options")
                if question[key] is not None
            }
            guide.append({**row, "question": semantic})
        messages = [
            {
                "role": "system",
                "content": (ASSETS / "master_prompt.md").read_text(encoding="utf-8"),
            },
        ]
        examples = json.loads(
            (ASSETS / "master_examples.json").read_text(encoding="utf-8")
        )
        for example in examples:
            # Doplnění null a uzavřenosti rozsahů podle stejného kontraktu.
            facts = [asdict(Fact.from_dict(fact)) for fact in example["facts"]]
            for fact in facts:
                if not fact["topic_ids"]:
                    fact["topic_ids"] = [
                        f"{q['questionnaire_id']}/{q['question_id']}"
                        for q in lookup_questions([fact["concept"]])["questions"]
                    ]
            validate_facts({"facts": facts}, MessageEvent(**example["message"]))
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": compact_json(
                            {
                                "message": _model_message(
                                    MessageEvent(**example["message"])
                                )
                            },
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": compact_json({"facts": facts}),
                    },
                ]
            )
        # ID pacienta a systémové časy extraktor k porozumění nepotřebuje.
        messages.append(
            {
                "role": "user",
                "content": compact_json(
                    {
                        "topic_catalog": guide,
                        "questionnaire_context": contexts,
                        "message": _model_message(message),
                        **(
                            {"clinical_fields": self.clinical_fields}
                            if self.clinical_fields
                            else {}
                        ),
                    }
                ),
            }
        )
        payload = self.client.structured_payload(
            messages, load_schema(), "patient_message_facts"
        )
        payload["max_completion_tokens"] = 8192
        return payload

    def __call__(self, message: MessageEvent) -> list[Fact]:
        return validate_facts(self.client.send(self.payload(message)), message)


def analyze_message(
    message: MessageEvent, extract: Callable[[MessageEvent], list[Fact]]
) -> dict:
    """Vrací kandidáty, ne hotový plán či pacientem potvrzené odpovědi.

    Popření a potíže pečujícího uchováme, ale samy nespouštějí dotaz pacientovi.
    ID témat se mapují přes katalog; vlastní extraktory bez ID mohou dál
    používat explicitní anglické aliasy. Nepokrytý pojem zůstává viditelný.
    """
    facts = extract(message)
    # A narrow conversational fallback requests the existing scale; it never
    # turns reassuring wording into a number or a denial of every symptom.
    normalized = "".join(
        c
        for c in unicodedata.normalize("NFKD", message.text.casefold())
        if not unicodedata.combining(c)
    ).strip(" \t\n.!?")
    if (
        not facts
        and message.source == "master_question"
        and message.author in {"patient", "caregiver"}
        and message.question
        in {
            "Jak se dnes cítíte?",
            "Jak se dnes cítí pacient, za kterého odpovídáte?",
        }
        and normalized
        in {"dobry", "dobre", "citim se dobre", "je mi dobre", "v pohode", "fajn"}
    ):
        facts = [
            Fact(
                "overall_feeling",
                "present",
                message.text,
                "patient",
                value=message.text,
                topic_ids=("nezadouci_ucinky/pocit",),
            )
        ]
    catalog = load_catalog()
    reasons: dict[tuple[str, str], list[int]] = {}
    unmapped, unknown_subject = [], []
    for index, fact in enumerate(facts):
        fallback = lookup_questions([fact.concept])
        packages = (
            resolve_topics(fact.topic_ids) if fact.topic_ids else fallback["questions"]
        )
        generic = {
            "nezadouci_ucinky/jine",
            "bolest_analgeticka_terapie/nu_jine",
            "esas/jiny",
        }
        if (
            not packages
            or (
                fact.topic_ids
                and set(fact.topic_ids) <= generic
                and fallback["unmapped_concepts"]
            )
        ) and fact.concept not in unmapped:
            unmapped.append(fact.concept)
        if fact.subject == "unknown":
            unknown_subject.append(index)
        if fact.subject != "patient" or fact.presence == "absent":
            continue
        for package in packages:
            ref = (package["questionnaire_id"], package["question_id"])
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
