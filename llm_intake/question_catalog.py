"""Úplný seznam ID z podkladů, malá počáteční mapa témat bez klinických pravidel."""

from collections.abc import Iterable
from pathlib import Path

from .core import DEFINITIONS, load_questions

# Toto jsou pouze vazby na otázky, nikoli úplná ontologie ani plán dotazování.
TOPIC_QUESTIONS = {
    "vomiting": (("nezadouci_ucinky", "zvraceni"),),
    "diarrhea": (("nezadouci_ucinky", "prujem"),),
    "fatigue": (("nezadouci_ucinky", "unava"),),
    "temperature": (("nezadouci_ucinky", "teplota"),),
    "breathlessness": (("nezadouci_ucinky", "dusnost"),),
    "bleeding": (
        ("nezadouci_ucinky", "krvaceni"),
        ("nezadouci_ucinky", "krvaceni_popis"),
    ),
}


def load_catalog(path: Path = DEFINITIONS) -> dict[tuple[str, str], dict]:
    catalog = {}
    for question in load_questions(path):
        ref = (question.questionnaire_id, question.id)
        catalog[ref] = question.specification()
    for refs in TOPIC_QUESTIONS.values():
        if any(ref not in catalog for ref in refs):
            raise ValueError("Mapa témat odkazuje na neexistující otázku.")
    return catalog


def lookup_questions(concepts: Iterable[str]) -> dict:
    """Vrátí vazby ke kontrole, ne rozhodnutí, že se tyto otázky mají položit.

    Například vomiting.episodes patří k tématu vomiting. Již známou hodnotu
    nemusí budoucí plánovač znovu zjišťovat. Nenamapované koncepty nezahazuje.
    """
    catalog = load_catalog()
    selected, unmapped = [], []
    for concept in concepts:
        refs = TOPIC_QUESTIONS.get(concept.split(".", 1)[0])
        if refs is None:
            if concept not in unmapped:
                unmapped.append(concept)
            continue
        for ref in refs:
            if ref not in selected:
                selected.append(ref)
    return {
        "questions": [catalog[ref] for ref in catalog if ref in selected],
        "unmapped_concepts": unmapped,
    }
