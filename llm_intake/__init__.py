"""Samostatný sběr jedné odpovědi, bez triáže a pacientské karty."""

from .core import (
    Intake,
    Question,
    create_targeted_session,
    find_question,
    load_question,
    load_questions,
)
from .flow import QuestionnaireFlow
from .master_contract import Fact, MessageEvent, NumericRange, build_packet
from .pipeline import build_pipeline_packet
from .question_catalog import load_catalog, lookup_questions

__all__ = [
    "Fact",
    "Intake",
    "MasterDialogue",
    "MasterExtractor",
    "MessageEvent",
    "NumericRange",
    "Question",
    "QuestionnaireFlow",
    "analyze_message",
    "build_packet",
    "build_pipeline_packet",
    "create_targeted_session",
    "find_question",
    "load_catalog",
    "load_question",
    "load_questions",
    "load_topic_catalog",
    "lookup_questions",
    "resolve_topics",
]


def __getattr__(name):
    # CLI python -m llm_intake.master / dialogue musí načíst modul až při spuštění.
    if name in {"MasterExtractor", "analyze_message"}:
        from . import master

        return getattr(master, name)
    if name == "MasterDialogue":
        from . import dialogue

        return getattr(dialogue, name)
    if name in {"load_topic_catalog", "resolve_topics"}:
        from . import question_catalog

        return getattr(question_catalog, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
