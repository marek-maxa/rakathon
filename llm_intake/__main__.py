"""CLI jedné otázky; integrace používá přímo Intake a Client."""

import argparse
import json
import sys

from triage import evaluate_intake

from .client import APIError, Client
from .core import DEFINITIONS, Intake, load_question


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MEDDI: odpověď → návrh → potvrzení nebo oprava"
    )
    parser.add_argument("--questionnaire", default="nezadouci_ucinky")
    parser.add_argument("--question", default="unava")
    parser.add_argument(
        "--max-clarifications",
        type=int,
        default=2,
        help="Limit doplňujících otázek (výchozí 2)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Vypsat interní JSON po potvrzení"
    )
    parser.add_argument(
        "--list", action="store_true", help="Vypsat otázky bez volání API"
    )
    args = parser.parse_args()
    if args.list:
        for form in json.loads(DEFINITIONS.read_text(encoding="utf-8")):
            print(form["id"])
            for q in form["otazky"]:
                print(f"  {q['id']}: {q['text']}")
        return 0
    try:
        question = load_question(args.questionnaire, args.question)
        client = Client.from_env()
        session = Intake(question, client, max_clarifications=args.max_clarifications)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Odpovězte prosím vlastními slovy. Pro ukončení napište /konec.")
    if question.options:
        print("Pokud Vám to pomůže, napište /moznosti pro nabídku odpovědí.")
    print(question.text)
    if question.instruction:
        print(question.instruction)
    if question.kind == "skala_1_10":
        print("Zadejte prosím hodnotu 1–10 podle definice dotazníku.")
    while session.state not in {"confirmed", "unresolved"}:
        try:
            if session.state == "needs_confirmation":
                print("\nZkontrolujte prosím, zda jsme Vám správně rozuměli:")
                print(session.patient_summary())
                answer = (
                    input("Je to správně? [ano/ne nebo /konec]: ").strip().casefold()
                )
                if answer == "/konec":
                    return 0
                if answer in {"ano", "a"}:
                    result = session.confirm()
                    print("Děkujeme, odpověď byla potvrzena.")
                    triage = evaluate_intake(result)
                    print(
                        f"Triáž (omezená sada pravidel): {triage['color'] or 'neurčeno'}"
                    )
                    if triage["requires_review"]:
                        print("Posouzení je neúplné; chybí další údaje pro triáž.")
                    if args.debug:
                        print("\nPotvrzený JSON pro navazující modul:")
                        print(
                            json.dumps(
                                result, ensure_ascii=False, indent=2, allow_nan=False
                            )
                        )
                elif answer in {"ne", "n"}:
                    session.reject()
                else:
                    print("Prosím odpovězte ano nebo ne.")
            else:
                label = (
                    session.next_question + " "
                    if session.state == "needs_correction"
                    else "Vaše odpověď: "
                )
                text = input(label)
                if text.strip().casefold() == "/konec":
                    return 0
                if text.strip().casefold() == "/moznosti":
                    print(
                        question.patient_options()
                        or "Tato otázka nemá nabídku odpovědí."
                    )
                    continue
                session.submit(text)
                if session.state == "needs_answer":
                    print(session.patient_summary())
        except (APIError, ValueError) as exc:
            print(f"Chyba: {exc}", file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print("\nUkončeno bez potvrzeného výstupu.")
            return 0
    if session.state == "unresolved":
        print(session.patient_summary())
        if args.debug:
            print(
                json.dumps(
                    session.snapshot(), ensure_ascii=False, indent=2, allow_nan=False
                )
            )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
