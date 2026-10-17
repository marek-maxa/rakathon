"""Export a visibly prepared offline demo; no LLM, SMTP or patient-store writes."""

import argparse
import json
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from llm_intake.core import Intake, load_question
from llm_intake.master_contract import Fact, MessageEvent
from llm_intake.pipeline import build_pipeline_packet
from main import compare_patients
from meddi.loader import list_patient_ids
from web.export import meddi_record
from web.triage import assess_contact

ROOT = Path(__file__).resolve().parents[1]


def prepare_cases(cases):
    """Reuse current adapters/rules; scenario titles and expectations stay outside."""
    prepared = []
    for case_index, case in enumerate(cases, 1):
        patient = {
            "patient_id": f"offline-{case_index}",
            "checkiny": [],
            **deepcopy(case["patient"]),
        }
        for checkin in patient["checkiny"]:
            checkin["patient_id"] = patient["patient_id"]
        steps = []
        previous_time = None
        for step_index, step in enumerate(case["steps"], 1):
            at = datetime.fromisoformat(step["at"])
            if at.utcoffset() is None or (previous_time and at <= previous_time):
                raise ValueError(
                    "Demo steps must have increasing timezone-aware times."
                )
            previous_time = at
            author = step.get("author", "patient")
            message = MessageEvent(
                id=f"offline-{case_index}-{step_index}",
                patient_id=patient["patient_id"],
                text=step["text"],
                available_at=at.isoformat(),
                source="master_question",
                author=author,
                question=(
                    "Jak se dnes cítí pacient, za kterého odpovídáte?"
                    if author == "caregiver"
                    else "Jak se dnes cítíte?"
                ),
            )
            facts = [
                Fact(
                    **{
                        "presence": "present",
                        "subject": "patient",
                        "evidence": message.text,
                        **fact,
                    }
                )
                for fact in step["facts"]
            ]
            answers, events = [], [asdict(message)]
            for answer_index, answer in enumerate(step.get("answers", []), 1):
                question = load_question(*answer["topic"].split("/"))
                value = answer["value"]
                text = (
                    question.options[value] if question.kind == "jedna" else str(value)
                )

                def extract(_question, sources, _questions, selected=value):
                    return {
                        "status": "answered",
                        "value": selected,
                        "source_index": len(sources) - 1,
                        "evidence": sources[-1],
                        "follow_up": None,
                    }

                intake = Intake(question, extract)
                event = MessageEvent(
                    id=f"{message.id}-answer-{answer_index}",
                    patient_id=patient["patient_id"],
                    text=text,
                    available_at=at.isoformat(),
                    source="targeted_answer",
                    author=author,
                    question=question.text,
                )
                intake.submit_event(event)
                intake.confirm()
                answers.append(intake)
                events.append(asdict(event))
            packet = build_pipeline_packet(message, facts, answers)
            packet["messages"] = events
            assessment = assess_contact(packet, patient, at)
            record = meddi_record(packet, at, assessment=assessment)["checkiny"][0]
            record["triage_assessment"] = assessment
            patient["checkiny"].append(record)
            steps.append(
                {
                    "time": at.strftime("%d. %m. %Y · %H:%M %z"),
                    "message": asdict(message),
                    "facts": packet["facts"],
                    "answers": packet["question_answers"],
                    "assessment": assessment,
                }
            )
        prepared.append(
            {
                "id": case["id"],
                "title": case["title"],
                "source": case["source"],
                "steps": steps,
            }
        )
    return prepared


def structured_baseline():
    """Existing evaluator only; reference data stays in its comparison branch."""
    patients = compare_patients(list_patient_ids(), with_messages=False)
    rows = [c for patient in patients for c in patient["checkins"]]
    counts = Counter(c["comparison"] for c in rows)
    return {
        "mode": "structured_only_without_messages",
        "patients": len(patients),
        "checkins": len(rows),
        "comparisons": {
            key: counts[key] for key in ("match", "lower", "higher", "undetermined")
        },
        "requires_review": sum(c["requires_review"] for c in rows),
    }


def build_demo(output: Path):
    cases = json.loads((ROOT / "demo/cases.json").read_text(encoding="utf-8"))
    prepared = prepare_cases(cases)
    baseline = structured_baseline()
    environment = Environment(
        loader=FileSystemLoader([ROOT / "demo", ROOT / "web/templates"]),
        autoescape=True,
    )
    html = environment.get_template("offline.html").render(
        cases=prepared,
        baseline=baseline,
        base_css=(ROOT / "web/static/style.css").read_text(encoding="utf-8"),
        triage_css=(ROOT / "web/static/triage.css").read_text(encoding="utf-8"),
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "results.json").write_text(
        json.dumps(
            {
                "mode": "prepared_offline_demo",
                "llm_called": False,
                "source": "demo/cases.json",
                "cases": prepared,
                "structured_baseline": baseline,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/demo")
    args = parser.parse_args()
    cases = build_demo(args.output)
    print(f"OFFLINE prepared demo: {len(cases)} cases; {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
