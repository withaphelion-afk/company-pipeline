import re
from urllib.parse import urlparse

_SUFFIX = re.compile(r"\b(inc|pvt|private|ltd|llc|limited|corp|corporation|co|technologies pvt)\b\.?", re.I)
_PUNCT = re.compile(r"[^\w\s]")


def normalize_name(name: str) -> str:
    s = _SUFFIX.sub(" ", name.lower())
    s = _PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def domain_of(url: str | None) -> str | None:
    """Canonical domain from a URL or bare host: lowercase, no scheme/path/www."""
    if not url:
        return None
    u = url.strip().lower()
    host = urlparse(u if "//" in u else f"//{u}").hostname or ""
    host = host.removeprefix("www.")
    return host if "." in host else None


def name_slug(name: str) -> str:
    return normalize_name(name).replace(" ", "")


_INVESTOR = re.compile(r"\b(investor|angel|venture|vc|general partner|managing partner|investment)\b", re.I)
_FOUNDER = re.compile(r"\b(co-?founder|founder|ceo|cto|chief executive|chief technology)\b", re.I)
_RECRUITER = re.compile(r"\b(talent|recruit\w*|people ops|people operations|head of hiring|hr)\b", re.I)
_EXEC = re.compile(r"\b(vp|vice president|head|director|chief|cfo|coo|cmo)\b", re.I)


def classify_role(title: str | None) -> str:
    t = title or ""
    if _INVESTOR.search(t):
        return "investor"
    if _FOUNDER.search(t):
        return "founder"
    if _RECRUITER.search(t):
        return "recruiter"
    if _EXEC.search(t):
        return "exec"
    return "other"


NOT_NAME_WORDS = {
    "platform", "match", "explore", "screens", "compare", "directory", "startup", "talent", "hiring", "managers", "recruiting",
    "recruiter", "recruitment", "ai", "chief", "executive", "officer", "technology", "operations", "president", "vice", "senior",
    "director", "head", "product", "engineering", "design", "customer", "success", "marketing", "sales", "advisor", "clinical",
    "board", "team", "careers", "about", "contact", "learn", "more", "blog", "press", "resume", "resumes", "ats", "demo",
    "pricing", "login", "solutions", "features", "cofounder", "co-founder", "ceo", "cto", "cfo", "coo", "the",
    "our", "your", "meet", "join", "get", "start", "book", "request", "see", "view", "read", "how", "why", "what", "ten", "x",
}
_ORG_AFTER_COMMA = re.compile(r",\s+(?!.*\b(chief|head|vp|svp|evp|director|officer|president|founder|manager|lead|engineer|counsel|ceo|cto|cfo|coo)\b)\S", re.I)


def is_person_name(name: str) -> bool:
    """Two or three capitalised words, none of them a page-heading or job-title word."""
    parts = re.sub(r"[^\w\s'-]", "", name).split()
    if not 2 <= len(parts) <= 3 or any(len(p) < 2 for p in parts):
        return False
    return not any(p.lower().strip("-'") in NOT_NAME_WORDS for p in parts)


def title_other_org(title: str | None, company_name: str) -> bool:
    """'CEO, Tier4 Group' on someone else's page: a customer quote, not an employee."""
    t = title or ""
    m = _ORG_AFTER_COMMA.search(t)
    return bool(m) and normalize_name(company_name) not in normalize_name(t)


def split_name(full_name: str) -> tuple[str, str] | None:
    parts = re.sub(r"[^\w\s'-]", "", full_name).split()
    return (parts[0].lower(), parts[-1].lower()) if len(parts) >= 2 else None


def candidate_emails(full_name: str, domain: str) -> list[tuple[str, str]]:
    """(address, pattern) candidates in priority order."""
    n = split_name(full_name)
    if not n:
        return []
    f, last = n
    return [
        (f"{f}.{last}@{domain}", "first.last"),
        (f"{f}@{domain}", "first"),
        (f"{f[0]}{last}@{domain}", "flast"),
        (f"{f}{last}@{domain}", "firstlast"),
        (f"{f}_{last}@{domain}", "first_last"),
    ]


def confidence(source: str, smtp: str) -> int:
    """source: direct|generated; smtp: valid|catch_all|unknown|not_checked|mx_none."""
    if source == "direct":
        return 90
    return {"valid": 80, "catch_all": 40, "not_checked": 30, "unknown": 10}.get(smtp, 10)
