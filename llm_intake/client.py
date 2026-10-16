"""Malý adaptér OpenAI kompatibilního Chat Completions API, bez SDK."""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from urllib import error, parse, request

from .core import Question, load_questions

ASSETS = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://apim-rakathon-q7146n.azure-api.net/openai/v1/"
DEFAULT_DEPLOYMENT = "gpt-6-1-sol-dz-eu"
MAX_TARGETED_EXAMPLES = 3


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class APIError(RuntimeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Přístupový klíč neposíláme na přesměrovaný endpoint.
        return None


@dataclass(frozen=True)
class Client:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_DEPLOYMENT
    key_header: str = "api-key"
    on_usage: Callable[[dict], None] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self):
        url = parse.urlsplit(self.base_url)
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise ValueError("Base URL musí být HTTPS bez přihlašovacích údajů.")
        if url.query or url.fragment:
            raise ValueError("Base URL nesmí obsahovat query ani fragment.")
        if not self.api_key.strip():
            raise ValueError("Chybí MEDDI_LLM_API_KEY.")
        if self.key_header not in {
            "Authorization",
            "api-key",
            "Ocp-Apim-Subscription-Key",
        }:
            raise ValueError("Nepodporovaná autentizační hlavička.")

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.environ.get("MEDDI_LLM_API_KEY", ""),
            base_url=os.environ.get("MEDDI_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("MEDDI_LLM_MODEL", DEFAULT_DEPLOYMENT),
            key_header=os.environ.get("MEDDI_LLM_KEY_HEADER", "api-key"),
        )

    def payload(
        self,
        question: Question,
        sources: list[str],
        source_questions: list[str | None] | None = None,
        source_events: list[dict | None] | None = None,
    ) -> dict:
        messages = [
            {
                "role": "system",
                "content": (ASSETS / "prompt.md").read_text(encoding="utf-8"),
            }
        ]
        examples = json.loads((ASSETS / "examples.json").read_text(encoding="utf-8"))
        # Příklady drží jen ID; texty a možnosti mají jediný zdroj v definicích.
        questions = {(q.questionnaire_id, q.id): q for q in load_questions()}
        # Stejná otázka má přednost, pak pouze stejný typ. Výběr je stabilní
        # a nezávisí na pacientově odpovědi; statický prefix zůstává opakovatelný.
        ref = {
            "questionnaire_id": question.questionnaire_id,
            "question_id": question.id,
        }
        relevant = [e for e in examples if e["input"]["question"] == ref]
        relevant.extend(
            e
            for e in examples
            if e["input"]["question"] != ref
            and questions[
                (
                    e["input"]["question"]["questionnaire_id"],
                    e["input"]["question"]["question_id"],
                )
            ].kind
            == question.kind
        )
        for example in relevant[:MAX_TARGETED_EXAMPLES]:
            ref = example["input"]["question"]
            example_input = {
                **example["input"],
                "question": questions[
                    (ref["questionnaire_id"], ref["question_id"])
                ].specification(),
            }
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": compact_json(example_input),
                    },
                    {
                        "role": "assistant",
                        "content": compact_json(example["output"]),
                    },
                ]
            )
        messages.append(
            {
                "role": "user",
                "content": compact_json(
                    {
                        "question": question.specification(),
                        "source_messages": sources,
                        "source_questions": source_questions
                        or [question.text] * len(sources),
                        "source_authors": [
                            event["author"] if event else "unknown"
                            for event in source_events
                        ]
                        if source_events is not None
                        else ["unknown"] * len(sources),
                    },
                ),
            }
        )
        return self.structured_payload(messages, question.schema(), "question_answer")

    def structured_payload(self, messages: list[dict], schema: dict, name: str) -> dict:
        """Sdílený tvar požadavku pro cílenou odpověď i extrakci celé zprávy."""
        return {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": 4096,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

    def __call__(
        self,
        question: Question,
        sources: list[str],
        source_questions: list[str | None] | None = None,
    ) -> dict:
        return self.send(self.payload(question, sources, source_questions))

    def send(self, payload: dict) -> dict:
        """Stejná autentizace a obsluha chyb pro oba extraktory."""
        auth = (
            f"Bearer {self.api_key}"
            if self.key_header == "Authorization"
            else self.api_key
        )
        req = request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=compact_json(payload).encode("utf-8"),
            headers={self.key_header: auth, "Content-Type": "application/json"},
            method="POST",
        )
        started = perf_counter()
        try:
            with request.build_opener(NoRedirect()).open(req, timeout=60) as response:
                body = json.load(response)
        except error.HTTPError as exc:
            if exc.code == 400:
                try:
                    detail = json.load(exc).get("error", {})
                    filtered = detail.get("code") == "content_filter"
                except (ValueError, TypeError, AttributeError, OSError):
                    filtered = False
                if filtered:
                    raise APIError(
                        "LLM API: HTTP 400 (content_filter). Obsahový filtr brány "
                        "odmítl požadavek; zpráva nebyla vyhodnocena."
                    ) from None
            if exc.code == 429:
                raise APIError(
                    "LLM API: HTTP 429. Brána omezila počet požadavků nebo tokenů; "
                    "počkejte a zkuste požadavek znovu s menším souběhem."
                ) from None
            if exc.code in {401, 403}:
                raise APIError(
                    f"LLM API: HTTP {exc.code}. Autentizace selhala; pro rakathonovou "
                    "bránu nastavte MEDDI_LLM_KEY_HEADER=api-key a ověřte klíč."
                ) from None
            if exc.code == 404:
                raise APIError(
                    "LLM API: HTTP 404. Ověřte base URL a přesný název nasazení "
                    "v MEDDI_LLM_MODEL (např. gpt-6-1-sol-dz-eu)."
                ) from None
            raise APIError(
                f"LLM API: HTTP {exc.code}. Ověřte parametry požadavku a podporu JSON schema."
            ) from None
        except (error.URLError, TimeoutError, OSError):
            raise APIError("LLM API není dostupné nebo vypršel časový limit.") from None
        except ValueError:
            raise APIError("LLM API nevrátilo platný JSON.") from None
        if self.on_usage is not None and isinstance(body, dict):
            usage = body.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            stats = {
                key: usage.get(key)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
            for field_name, detail, key in (
                ("cached_tokens", "prompt_tokens_details", "cached_tokens"),
                ("reasoning_tokens", "completion_tokens_details", "reasoning_tokens"),
            ):
                nested = usage.get(detail)
                stats[field_name] = (
                    nested.get(key) if isinstance(nested, dict) else None
                )
            stats = {
                key: value if type(value) is int and value >= 0 else None
                for key, value in stats.items()
            }
            self.on_usage(
                {
                    **stats,
                    "latency_ms": round((perf_counter() - started) * 1000),
                    "schema": payload["response_format"]["json_schema"]["name"],
                }
            )
        try:
            choice = body["choices"][0]
            if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
                raise APIError(
                    "Model odmítl odpověď nebo je výstup neúplný; návrh nebyl změněn."
                )
            return json.loads(choice["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise APIError("LLM API vrátilo neplatnou strukturu odpovědi.") from None

    def extract_events(
        self, question, sources, source_questions, source_events
    ) -> dict:
        return self.send(
            self.payload(question, sources, source_questions, source_events)
        )
