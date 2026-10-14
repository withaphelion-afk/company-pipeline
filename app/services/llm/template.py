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

    @staticmethod
    def _why(inp: DraftInput, sig: dict[str, Any]) -> str:
        """One sentence on why this person/company: the matching job for hiring, else their own one-liner, else the signal."""
        value = sig["value"].removeprefix("Job: ")
        if inp.intent == "hire" and sig["type"] == "hiring" and value:
            return f'I noticed {inp.company} is hiring: "{value}".'
        if inp.company_desc:
            return f"I have been following {inp.company}: {inp.company_desc.strip().rstrip('.')}."
        if value:
            return f'{LEAD.get(sig["type"], LEAD["news"])} at {inp.company}: "{value}".'
        return f"I came across {inp.company} and the work you are doing there."

    def followup(self, kind: str, inp: DraftInput) -> str:
        """Body for a follow-up ('followup') or the closing note ('final'); same facts as the first email."""
        p = inp.profile
        roles = p.get("target_roles") or [p.get("role", "engineering")]
        proj = pick_project(p.get("projects") or [], inp.company_text) or {"name": "my work", "link": ""}
        featured = [x for x in p.get("projects") or [] if x.get("featured")] or [proj]
        return self.env.get_template(f"{kind}.j2").render(
            first=inp.person_name.split()[0], company=inp.company, me=p["name"], project=proj, projects=featured,
            project_names=" and ".join(x["name"] for x in featured), target_role=roles[0]).strip()

    def draft(self, inp: DraftInput) -> dict[str, str]:
        p = inp.profile
        sig: dict[str, Any] = inp.signals[0] if inp.signals else {"type": "news", "value": "", "url": None}
        proj = pick_project(p.get("projects") or [], inp.company_text)
        featured = [x for x in p.get("projects") or [] if x.get("featured")] or ([proj] if proj else [])
        roles = p.get("target_roles") or [p.get("role", "engineering")]
        ctx = {
            "first": inp.person_name.split()[0],
            "company": inp.company,
            "lead": LEAD.get(sig["type"], LEAD["news"]),
            "signal": sig["value"].removeprefix("Job: "),
            "me": p["name"],
            "role": p.get("role", "engineer"),
            "location": p.get("location", ""),
            "skills": ", ".join((p.get("skills") or [])[:3]),
            "project": proj,
            "projects": featured,
            "project_names": " or ".join(x["name"] for x in featured),
            "target_role": roles[0],
            "intent": inp.intent,
            "why": self._why(inp, sig),
        }
        body = self.env.get_template(f"outreach_{inp.intent if inp.intent in ('hire', 'invest', 'advise') else 'hire'}.j2").render(**ctx).strip()
        subject = self.env.get_template("subject.j2").render(**ctx).strip()
        return {"subject": subject, "body": body}
