from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.llm.base import DraftInput, LLMProvider

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "templates"
LEAD = {
    "funding": "I saw the recent funding news",
    "launch": "I noticed a recent launch",
    "hiring": "I noticed you are hiring",
    "post": "I read your latest post",
    "talk": "I came across a recent talk",
    "news": "I came across recent coverage",
}


class TemplateProvider(LLMProvider):
    name = "template"

    def __init__(self) -> None:
        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), undefined=StrictUndefined, trim_blocks=True)

    def draft(self, inp: DraftInput) -> dict[str, str]:
        p = inp.profile
        sig = inp.signals[0]
        proj = (p.get("projects") or [None])[0]
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
        }
        body = self.env.get_template("outreach.j2").render(**ctx).strip()
        subject = self.env.get_template("subject.j2").render(**ctx).strip()
        return {"subject": subject, "body": body}
