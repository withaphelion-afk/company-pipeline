import json
import re
from dataclasses import dataclass
from typing import Any

PROMPT_VERSION = "v1"
OPT_OUT_RE = re.compile(r"opt[- ]?out|unsubscribe|not interested|prefer not", re.I)


class LLMError(Exception):
    pass


@dataclass
class DraftInput:
    profile: dict[str, Any]
    person_name: str
    person_title: str | None
    role_type: str
    company: str
    signals: list[dict[str, Any]]  # {type, value, url}
    intent: str = "hire"  # hire | invest | advise
    company_text: str = ""  # description + industry, used to pick the most relevant project


class LLMProvider:
    name = ""

    def available(self) -> bool:
        return True

    def draft(self, inp: DraftInput) -> dict[str, str]:
        raise NotImplementedError


def parse_draft_json(text: str) -> dict[str, str]:
    """Strip code fences, parse JSON, require subject/body strings."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        d = json.loads(t)
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON: {e}") from e
    if not isinstance(d, dict) or not isinstance(d.get("subject"), str) or not isinstance(d.get("body"), str):
        raise LLMError("JSON must contain string fields subject and body")
    return {"subject": d["subject"].strip(), "body": d["body"].strip()}


def validate_draft(d: dict[str, str]) -> None:
    n = len(d["body"].split())
    if not 80 <= n <= 120:
        raise LLMError(f"body has {n} words, need 80-120")
    if not d["subject"]:
        raise LLMError("empty subject")
    if not OPT_OUT_RE.search(d["body"]):
        raise LLMError("missing opt-out sentence")
