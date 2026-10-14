"""Relevance of a person to the profile: score 0-100, intent (hire / invest / advise) and a short reason."""
import re
from typing import Any

STOP = {"with", "that", "this", "from", "your", "have", "will", "team", "work", "open", "roles", "role", "including", "and", "for", "the", "our"}
BASE = {"investor": 35, "recruiter": 35, "founder": 30, "exec": 25, "other": 8}


def tokens(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z+.#-]{2,}", (text or "").lower()) if w not in STOP}


def profile_terms(profile: dict[str, Any]) -> set[str]:
    t = tokens(" ".join(profile.get("skills") or []) + " " + " ".join(profile.get("target_roles") or []))
    for p in profile.get("projects") or []:
        t |= {x.lower() for x in p.get("tags") or []}
    return t


def score_person(role: str, company: Any, signals: list[Any], profile: dict[str, Any], best_conf: int,
                 connection: bool = False) -> tuple[int, str, str]:
    terms = profile_terms(profile)
    reasons: list[str] = []
    score = BASE.get(role, 8)
    hiring = [s for s in signals if s.type == "hiring"]
    jobs = [s for s in hiring if s.value.startswith("Job: ")]  # already filtered to the saved role + remote search
    match = sorted(terms & tokens(" ".join(s.value for s in hiring)))
    if jobs:
        score += 30
        match = match or ["job"]
        reasons.append("remote job: " + jobs[0].value[5:70])
    elif match:
        score += 25
        reasons.append("hiring for " + ", ".join(match[:3]))
    elif hiring or company.is_hiring:
        score += 10
        reasons.append("is hiring")
    if any(s.type == "funding" for s in signals):
        score += 10
        reasons.append("recent funding news")
    overlap = sorted(terms & tokens(f"{company.description or ''} {company.industry or ''}"))
    if overlap:
        score += min(20, 5 * len(overlap))
        reasons.append("same space: " + ", ".join(overlap[:3]))
    if connection:
        score += 25
        reasons.append("your LinkedIn connection")
    score += min(9, best_conf // 10)
    if role == "investor" or (company.extra or {}).get("kind") == "investor":
        intent = "invest"
    elif role == "recruiter" or (role in ("founder", "exec") and match):
        intent = "hire"
    else:
        intent = "advise"
    return min(100, score), intent, "; ".join(reasons) or f"{role} at {company.name}"
