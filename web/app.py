import os
import secrets
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "llm_intake" / ".env")
sys.path.insert(0, str(ROOT))

from llm_intake import Intake, QuestionnaireFlow, build_pipeline_packet
from llm_intake.client import APIError, Client
from llm_intake.master import MasterExtractor, analyze_message
from llm_intake.master_contract import Fact, MessageEvent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
MASTER_QUESTION = "Jak se dnes cítíte?"
sessions = {}


def state():
    key = session.get("id")
    if key not in sessions:
        key = session["id"] = secrets.token_urlsafe(16)
        sessions[key] = {
            "message": None,
            "analysis": None,
            "flow": None,
            "intake": None,
            "done": False,
        }
    return key, sessions[key]


def next_intake(data, client):
    flow = data["flow"]
    data["intake"] = None
    while flow and (question := flow.next_question()):
        intake = Intake(question, client)
        intake.submit(data["message"].text, source_question=MASTER_QUESTION)
        if intake.state == "needs_confirmation":
            flow.record(intake)
        else:
            data["intake"] = intake
            break


def page_for(data):
    if data["message"] is None:
        return {"master": True, "question": MASTER_QUESTION}
    intake = data["intake"]
    if intake:
        return {
            "question": intake.next_question
            if intake.state != "unresolved"
            else intake.question.text,
            "instruction": intake.question.instruction,
            "unresolved": intake.patient_summary()
            if intake.state == "unresolved"
            else None,
        }
    flow = data["flow"]
    return {
        "done": data["done"],
        "review": True,
        "master_text": data["message"].text,
        "drafts": flow.sessions if flow else (),
        "gaps": not data["analysis"]["question_candidates"]
        or bool(data["analysis"]["unmapped_concepts"])
        or bool(data["analysis"]["unknown_subject_fact_indices"]),
        "blocked": flow and flow.snapshot()["state"] == "blocked",
    }


@app.route("/", methods=["GET", "POST"])
def index():
    key, saved = state()
    error = None
    data = saved
    if request.method == "POST":
        data = deepcopy(saved)
        try:
            if data["done"]:
                raise ValueError("Odpovědi už jsou potvrzené.")
            if "restart" in request.form:
                sessions.pop(key)
                return redirect("/")
            if "confirm" in request.form:
                if data["message"] is None or data["intake"] is not None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                drafts = data["flow"].sessions if data["flow"] else ()
                for draft in drafts:
                    if draft.state == "needs_confirmation":
                        draft.confirm()
                facts = [
                    Fact.from_dict(
                        {
                            k: v
                            for k, v in fact.items()
                            if k not in {"source_message_id", "confirmation"}
                        }
                    )
                    for fact in data["analysis"]["facts"]
                ]
                data["packet"] = build_pipeline_packet(data["message"], facts, drafts)
                data["packet"]["questionnaire_flow"] = (
                    data["flow"].snapshot() if data["flow"] else None
                )
                data["done"] = True
            elif "edit" in request.form:
                if not page_for(data).get("review") or data["flow"] is None:
                    raise ValueError("Odpovědi lze opravit v závěrečném souhrnu.")
                drafts = data["flow"].sessions
                position = int(request.form["edit"])
                if not 0 <= position < len(drafts):
                    raise ValueError("Neplatná otázka.")
                previous = data["flow"]
                flow = QuestionnaireFlow(
                    previous.questionnaire_id,
                    targets=previous.snapshot()["targets"],
                    allow_drafts=True,
                )
                for draft in drafts[:position]:
                    flow.record(draft)
                intake = drafts[position]
                if intake.state == "needs_confirmation":
                    intake.reject()
                else:
                    intake = Intake(intake.question, Client.from_env())
                data["flow"], data["intake"] = flow, intake
            elif "continue" in request.form:
                intake = data["intake"]
                if intake is None or intake.state != "unresolved":
                    raise ValueError("Není nevyřešená odpověď k přeskočení.")
                data["flow"].record(intake)
                next_intake(data, Client.from_env())
            elif "answer" in request.form:
                text = request.form["answer"].strip()
                if not text:
                    raise ValueError("Odpověď nesmí být prázdná.")
                client = Client.from_env()
                if data["message"] is None:
                    message = MessageEvent(
                        id=secrets.token_urlsafe(16),
                        patient_id=key,
                        text=text,
                        available_at=datetime.now(UTC).isoformat(),
                        source="master_question",
                        author="patient",
                        question=MASTER_QUESTION,
                    )
                    analysis = analyze_message(message, MasterExtractor(client))
                    candidates = [
                        item["question"] for item in analysis["question_candidates"]
                    ]
                    ids = {q["question_id"] for q in candidates}
                    targets = [
                        q["question_id"]
                        for q in candidates
                        if not q["condition"] or q["condition"].split(":")[0] not in ids
                    ]
                    flow = (
                        QuestionnaireFlow(
                            candidates[0]["questionnaire_id"],
                            targets=targets,
                            allow_drafts=True,
                        )
                        if targets
                        else None
                    )
                    data.update(message=message, analysis=analysis, flow=flow)
                    next_intake(data, client)
                else:
                    intake = data["intake"]
                    if intake is None:
                        raise ValueError("Nyní zkontrolujte souhrn odpovědí.")
                    intake.submit(text)
                    if intake.state == "needs_confirmation":
                        data["flow"].record(intake)
                        next_intake(data, client)
            else:
                raise ValueError("Neplatná akce formuláře.")
            sessions[key] = data
            return redirect("/")
        except (APIError, ValueError, TypeError) as exc:
            error = str(exc)
            data = saved
    return render_template("index.html", page=page_for(data), error=error)


if __name__ == "__main__":
    app.run()
