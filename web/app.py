import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, session

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "llm_intake" / ".env")
sys.path.insert(0, str(ROOT))

from llm_intake import Intake, load_question
from llm_intake.client import APIError, Client
from meddi.loader import list_patient_ids, load_patient
from web.patient_report import patient_report

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
app.config["BASIC_AUTH_USERNAME"] = os.environ.get("MEDDI_BASIC_AUTH_USERNAME", "")
app.config["BASIC_AUTH_PASSWORD"] = os.environ.get("MEDDI_BASIC_AUTH_PASSWORD", "")
app.register_blueprint(patient_report)
questions = [
    load_question("nezadouci_ucinky", name)
    for name in ("pocit", "sobestacnost", "ucinky")
]
sessions = {}


@app.before_request
def require_basic_auth():
    """Protect every route, including reports and static files; fail closed."""
    username = app.config["BASIC_AUTH_USERNAME"]
    password = app.config["BASIC_AUTH_PASSWORD"]
    if not username or not password or ":" in username:
        return Response(
            "Web authentication is not configured.",
            status=503,
            headers={"Cache-Control": "no-store"},
            mimetype="text/plain",
        )
    auth = request.authorization
    if auth is not None and auth.type == "basic":
        username_matches = secrets.compare_digest(
            (auth.username or "").encode("utf-8"), username.encode("utf-8")
        )
        password_matches = secrets.compare_digest(
            (auth.password or "").encode("utf-8"), password.encode("utf-8")
        )
        if username_matches and password_matches:
            return None
    return Response(
        "Authentication required.",
        status=401,
        headers={
            "WWW-Authenticate": 'Basic realm="MEDDI demo", charset="UTF-8"',
            "Cache-Control": "no-store",
        },
        mimetype="text/plain",
    )


def patient_choices():
    return [
        {
            "id": patient_id,
            "name": load_patient(patient_id)["demografie"]["jmeno_fiktivni"],
        }
        for patient_id in list_patient_ids()
    ]


def state():
    key = session.get("id")
    if key not in sessions:
        key = session["id"] = secrets.token_urlsafe(16)
        sessions[key] = {"index": 0, "intake": None, "patient_id": None}
    data = sessions[key]
    if data["patient_id"] is None:
        return {
            "select_patient": True,
            "patients": patient_choices(),
        }, data
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
        "patient_id": data["patient_id"],
        "patient_name": data["patient_name"],
    }
    if intake and intake.state == "unresolved":
        page["unresolved"] = intake.patient_summary()
    return page, data


@app.route("/", methods=["GET", "POST"])
def index():
    page, data = state()
    error = None
    if request.method == "POST":
        try:
            if page.get("select_patient"):
                selected_id = request.form.get("patient_id", "")
                selected_patient = next(
                    (
                        patient
                        for patient in page["patients"]
                        if patient["id"] == selected_id
                    ),
                    None,
                )
                if selected_patient is None:
                    raise ValueError("Vyberte platný profil pacienta.")
                data["patient_id"] = selected_id
                data["patient_name"] = selected_patient["name"]
            else:
                intake = data["intake"]
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
                    if intake is None or intake.state != "needs_confirmation":
                        raise ValueError("Nejprve zadejte odpověď.")
                    data["answers"] = data.get("answers", [])
                    data["answers"].append(intake.confirm(value))
                    data["index"] += 1
                    data["intake"] = None
            return redirect("/")
        except (APIError, ValueError, TypeError) as exc:
            error = str(exc)
            page, data = state()
            if page.get("select_patient"):
                page["selected_patient"] = request.form.get("patient_id", "")

    if page.get("intake") and page["intake"].state == "needs_confirmation":
        question = questions[data["index"]]
        page["value"] = page["intake"].snapshot()["extraction"]["value"]
        page["options"] = question.options
        page["kind"] = question.kind
        page["summary"] = page["intake"].patient_summary()
    return render_template("index.html", page=page, error=error)


if __name__ == "__main__":
    app.run()
