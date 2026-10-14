import json

import httpx

from app.core.config import get_settings
from app.services.llm.base import DraftInput, LLMError, LLMProvider, parse_draft_json, validate_draft

SYSTEM = (
    "You write short, honest outreach emails. Use ONLY the facts provided below. Never invent achievements, "
    "metrics, employers or claims. Mention at least one specific detail from the signals. Body: 80-120 words, "
    "plain text, include one sentence telling the recipient they can reply 'opt out' to never be contacted again. "
    'Return ONLY JSON: {"subject": "...", "body": "..."}'
)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self.url, self.model = s.OLLAMA_URL.rstrip("/"), s.OLLAMA_MODEL
        self._http = httpx.Client(timeout=120.0, transport=transport)

    def available(self) -> bool:
        try:
            return self._http.get(f"{self.url}/api/tags", timeout=3.0).status_code == 200
        except httpx.HTTPError:
            return False

    def _generate(self, prompt: str) -> str:
        try:
            r = self._http.post(
                f"{self.url}/api/generate",
                json={"model": self.model, "system": SYSTEM, "prompt": prompt, "stream": False, "format": "json"},
            )
            r.raise_for_status()
            return str(r.json()["response"])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(f"ollama request failed: {e}") from e

    def draft(self, inp: DraftInput) -> dict[str, str]:
        facts = {
            "sender": inp.profile,
            "recipient": {"name": inp.person_name, "title": inp.person_title, "company": inp.company},
            "signals": inp.signals,
            "goal": {"hire": "ask about a role", "invest": "share a product and ask for feedback or backing", "advise": "ask for advice"}.get(inp.intent, "introduce"),
        }
        prompt = json.dumps(facts, ensure_ascii=False)
        last: LLMError | None = None
        for _ in range(2):  # one retry, then the caller falls back to the template
            try:
                d = parse_draft_json(self._generate(prompt))
                validate_draft(d)
                return d
            except LLMError as e:
                last = e
                prompt += f"\nPrevious attempt rejected: {e}. Fix it."
        raise last or LLMError("unknown")
