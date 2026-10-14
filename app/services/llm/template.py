from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.llm.base import DraftInput, LLMProvider
from app.services.relevance import tokens

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "templates"
LEAD = {
    "funding": "I saw the recent funding news",
    "launch": "I noticed a recent launch",
    "hiring": "I noticed you are hiring",
    "post": "I read your latest post",
    "talk": "I came across a recent talk",
    "news": "I came across recent coverage",
}


def pick_project(projects: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
    """Project whose tags overlap most with the company text; first project when nothing matches."""
    if not projects:
        return None
    words = tokens(text)
    return max(projects, key=lambda pr: len({t.lower() for t in pr.get("tags") or []} & words))


class TemplateProvider(LLMProvider):
    name = "template"

    def __init__(self) -> None:
        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), undefined=StrictUndefined, trim_blocks=True)

    def draft(self, inp: DraftInput) -> dict[str, str]:
        p = inp.profile
        sig = inp.signals[0]
        proj = pick_project(p.get("projects") or [], inp.company_text)
        roles = p.get("target_roles") or [p.get("role", "engineering")]
        ctx = {
            "first": inp.person_name.split()[0],
            "company": inp.company,
            "lead": LEAD.get(sig["type"], LEAD["news"]),
            "signal": sig["value"],
            "me": p["name"],
            "role": p.get("role", "engineer"),
            "location": p.get("location", ""),
            "skills": ", ".join((p.get("skills") or [])[:3]),
            "project": proj,
            "target_role": roles[0],
            "intent": inp.intent,
        }
        body = self.env.get_template(f"outreach_{inp.intent if inp.intent in ('hire', 'invest', 'advise') else 'hire'}.j2").render(**ctx).strip()
        subject = self.env.get_template("subject.j2").render(**ctx).strip()
        return {"subject": subject, "body": body}
