"""Úplný katalog témat a mechanické vazby na zdrojové otázky."""

import json
from collections.abc import Iterable
from pathlib import Path

from .core import DEFINITIONS, load_questions

TOPICS = Path(__file__).with_name("question_topics.json")

# Organizační rozcestníky lze při známé konkrétní potíži přeskočit. Ostatní
# podmínění rodiče (např. krvaceni a nu) musejí zůstat ve flow před popisem.
GATEWAYS = {
    f"nezadouci_ucinky/{q}" for q in ("ucinky", "nnz_typ", "stolice_typ", "bolesti_typ")
}


def load_catalog(path: Path = DEFINITIONS) -> dict[tuple[str, str], dict]:
    catalog = {}
    for question in load_questions(path):
        ref = (question.questionnaire_id, question.id)
        catalog[ref] = question.specification()
    return catalog


def load_topic_catalog(
    path: Path = DEFINITIONS, topics_path: Path = TOPICS
) -> dict[str, dict]:
    """Chybějící i nadbytečná položka je chyba, nikoli tiché zúžení promptu."""
    questions = load_catalog(path)
    metadata = json.loads(topics_path.read_text(encoding="utf-8"))
    expected = {f"{form}/{question}" for form, question in questions}
    if set(metadata) != expected:
        raise ValueError(
            f"Neúplný katalog témat: chybí {sorted(expected - set(metadata))}, navíc {sorted(set(metadata) - expected)}"
        )
    result = {}
    for (form, question), package in questions.items():
        topic_id = f"{form}/{question}"
        row = metadata[topic_id]
        if set(row) != {"keywords", "concepts", "hint"}:
            raise ValueError(f"Neplatná pole tématu: {topic_id}")
        if not isinstance(row["hint"], str) or not row["hint"].strip():
            raise ValueError(f"Chybí kontext tématu: {topic_id}")
        for name in ("keywords", "concepts"):
            if (
                not isinstance(row[name], list)
                or not row[name]
                or not all(isinstance(v, str) and v.strip() for v in row[name])
            ):
                raise ValueError(f"Neplatný slovník tématu: {topic_id}/{name}")
        result[topic_id] = {"topic_id": topic_id, **row, "question": package}
    return result


def resolve_topics(topic_ids: Iterable[str]) -> list[dict]:
    """Přesná ID → balíčky včetně podmíněných rodičů mimo rozcestníky."""
    catalog = load_topic_catalog()
    selected = set(topic_ids)
    if not selected <= catalog.keys():
        raise ValueError("Neznámé ID tématu.")
    for topic_id in list(selected):
        package = catalog[topic_id]["question"]
        condition = package["condition"]
        if condition:
            parent_id = f"{package['questionnaire_id']}/{condition.split(':')[0]}"
            if parent_id not in GATEWAYS:
                selected.add(parent_id)
    return [
        row["question"] for topic_id, row in catalog.items() if topic_id in selected
    ]


def lookup_questions(concepts: Iterable[str]) -> dict:
    """Vrátí vazby ke kontrole, ne rozhodnutí, že se tyto otázky mají položit.

    Například vomiting.episodes patří k tématu vomiting. Již známou hodnotu
    nemusí budoucí plánovač znovu zjišťovat. Nenamapované koncepty nezahazuje.
    """
    catalog = load_topic_catalog()
    aliases: dict[str, list[str]] = {}
    for topic_id, row in catalog.items():
        for concept in row["concepts"]:
            aliases.setdefault(concept, []).append(topic_id)
    selected, unmapped = [], []
    for concept in concepts:
        key = concept
        while key not in aliases and "." in key:
            key = key.rsplit(".", 1)[0]
        refs = aliases.get(key)
        if refs is None:
            if concept not in unmapped:
                unmapped.append(concept)
            continue
        for ref in refs:
            if ref not in selected:
                selected.append(ref)
    return {
        "questions": resolve_topics(selected),
        "unmapped_concepts": unmapped,
    }
