import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "llm_intake" / ".env")
sys.path.insert(0, str(ROOT))

from llm_intake import Intake, load_question
from llm_intake.client import APIError, Client

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
questions = [
    load_question("nezadouci_ucinky", name)
    for name in ("pocit", "sobestacnost", "ucinky")
]
sessions = {}


def state():
    key = session.get("id")
    if key not in sessions:
        key = session["id"] = secrets.token_urlsafe(16)
        sessions[key] = {"index": 0, "intake": None}
    data = sessions[key]
    intake = data["intake"]
    if data["index"] == len(questions):
        return {"done": True}, data
    question = questions[data["index"]]
    page = {
        "question": (
            intake.next_question
            if intake and intake.state in {"needs_answer", "needs_correction"}
            else question.text
        ),
        "instruction": question.instruction if intake is None else None,
        "intake": intake,
        "number": data["index"] + 1,
        "total": len(questions),
    }
    if intake and intake.state == "unresolved":
        page["unresolved"] = intake.patient_summary()
    return page, data


@app.route("/", methods=["GET", "POST"])
def index():
    page, data = state()
    error = None
    if request.method == "POST":
        intake = data["intake"]
        try:
            if "continue" in request.form:
                if intake is None or intake.state != "unresolved":
                    raise ValueError("Není nevyřešená odpověď k přeskočení.")
                data["answers"] = data.get("answers", [])
                data["answers"].append(intake.snapshot())
                data["index"] += 1
                data["intake"] = None
            elif "answer" in request.form:
                if not request.form["answer"].strip():
                    raise ValueError("Odpověď nesmí být prázdná.")
                if not os.environ.get("MEDDI_LLM_API_KEY", "").strip():
                    raise ValueError("Chybí MEDDI_LLM_API_KEY.")
                if intake is None:
                    intake = data["intake"] = Intake(
                        questions[data["index"]], Client.from_env()
                    )
                intake.submit(request.form["answer"])
            else:
                question = questions[data["index"]]
                value = request.form.get("value", "")
                if question.kind == "jedna":
                    value = int(value)
                elif question.kind == "vice":
                    value = [int(index) for index in request.form.getlist("value")]
                data["answers"] = data.get("answers", [])
                data["answers"].append(intake.confirm(value))
                data["index"] += 1
                data["intake"] = None
            return redirect("/")
        except (APIError, ValueError, TypeError) as exc:
            error = str(exc)
            page, data = state()

    if page.get("intake") and page["intake"].state == "needs_confirmation":
        question = questions[data["index"]]
        page["value"] = page["intake"].snapshot()["extraction"]["value"]
        page["options"] = question.options
        page["kind"] = question.kind
        page["summary"] = page["intake"].patient_summary()
    return render_template("index.html", page=page, error=error)


if __name__ == "__main__":
    app.run()
