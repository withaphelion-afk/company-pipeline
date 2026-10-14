"""Company website About/Team/Contact pages: published founder names, titles and emails. robots.txt enforced."""
import re
from collections.abc import Iterable

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.services.normalize import split_name
from app.sources.base import CompanyLike, PersonRaw, SignalRaw, Source

PATHS = ["/about", "/team", "/contact", "/company"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
NAME_RE = re.compile(r"^[A-Z][a-zA-Z'.-]+(?: [A-Z][a-zA-Z'.-]+){1,2}$")
TITLE_RE = re.compile(
    r"\b(co-?founder|founder|ceo|cto|coo|cfo|chief|head of|director|vp|vice president|recruiter|talent|people ops|hiring)\b",
    re.I,
)
SPLIT_RE = re.compile(r"\s*(?:,|\||—|–| - )\s*")
JUNK_EMAILS = ("example.", "sentry", "wixpress", ".png", ".jpg", ".svg")


def extract_people(html: str, page_url: str) -> list[PersonRaw]:
    tree = HTMLParser(html)
    for node in tree.css("script,style,noscript"):
        node.decompose()
    emails = {e.lower() for e in EMAIL_RE.findall(html)}
    emails = {e for e in emails if not any(j in e for j in JUNK_EMAILS)}
    lines = [ln.strip() for ln in (tree.body.text(separator="\n") if tree.body else "").splitlines() if ln.strip()]
    found: dict[str, str] = {}
    for i, ln in enumerate(lines):
        if len(ln) > 90:
            continue
        parts = SPLIT_RE.split(ln, maxsplit=1)
        if len(parts) == 2 and NAME_RE.match(parts[0]) and TITLE_RE.search(parts[1]):
            found.setdefault(parts[0], parts[1])
        elif TITLE_RE.search(ln) and i > 0 and NAME_RE.match(lines[i - 1]):
            found.setdefault(lines[i - 1], ln)
    people = []
    for name, title in found.items():
        n = split_name(name)
        mail = next((e for e in sorted(emails) if n and any(p in e.split("@")[0] for p in n)), None)
        people.append(
            PersonRaw(full_name=name, title=title, source="company_site", email=mail, email_url=page_url if mail else None)
        )
    return people


class CompanySite(Source):
    name = "company_site"

    def fetch_signals(self, company: CompanyLike) -> Iterable[SignalRaw]:
        """Most recent post/talk link if the site exposes a /blog index."""
        if not company.domain:
            return
        base = f"https://{company.domain}"
        html = self.client.get_text(f"{base}/blog", html=True)
        if not html:
            return
        for a in HTMLParser(html).css("a[href]"):
            href = a.attributes.get("href") or ""
            title = (a.text() or "").strip()
            if "/blog/" in href and len(title) > 8:
                url = href if href.startswith("http") else base + (href if href.startswith("/") else "/" + href)
                yield SignalRaw("post", title, self.name, url)
                return

    def fetch_people(self, company: CompanyLike) -> Iterable[PersonRaw]:
        if not company.domain:
            return
        seen: set[str] = set()
        for path in PATHS:
            url = f"https://{company.domain}{path}"
            html = self.client.get_text(url, html=True)  # None when disallowed by robots.txt or missing
            if html:
                for p in extract_people(html, url):
                    if p.full_name not in seen:
                        seen.add(p.full_name)
                        yield p
