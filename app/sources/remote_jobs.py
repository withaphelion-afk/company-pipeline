"""Free remote-job feeds (no keys): Hacker News 'Who is hiring', RemoteOK, Remotive, We Work Remotely.

Terms: RemoteOK and Remotive ask for a link back to them if their data is shown publicly and for modest request
rates; this app is private and fetches a handful of times per run. HN data comes from the public Algolia HN API.
"""
import re
from calendar import timegm
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import feedparser
from selectolax.lexbor import LexborHTMLParser

from app.sources.base import CompanyRaw, PersonRaw, SignalRaw, Source

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SKIP_LINK = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "github.com", "linkedin.com", "twitter.com", "x.com",
             "ycombinator.com", "notion.so", "google.com", "forms.gle", "bit.ly", "wellfound.com", "smartrecruiters.com",
             "workday", "breezy.hr", "recruitee.com", "jobs.", "careers.")


def _job_signal(source: str, title: str, location: str, url: str | None, when: datetime | None = None) -> SignalRaw:
    return SignalRaw("hiring", f"Job: {title} ({location or 'Remote'})", source, url, when or datetime.now(UTC))


class HnHiring(Source):
    """Latest 'Ask HN: Who is hiring?' thread: top-level comments are job posts, many with a contact email."""

    name = "hn_hiring"
    seed = True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        hits = (self.client.get_json("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=6") or {}).get("hits", [])
        story = next((h for h in hits if "who is hiring" in (h.get("title") or "").lower()), None)
        if not story:
            return
        thread = self.client.get_json(f"https://hn.algolia.com/api/v1/items/{story['objectID']}") or {}
        for c in thread.get("children", []):
            raw = self._parse(c)
            if raw:
                yield raw

    def _parse(self, c: dict[str, Any]) -> CompanyRaw | None:
        html = c.get("text") or ""
        if not html:
            return None
        tree = LexborHTMLParser(f"<div>{html}</div>")
        lines = [ln.strip() for ln in (tree.body.text(separator="\n") if tree.body else "").splitlines() if ln.strip()]
        if not lines:
            return None
        header = lines[0]
        parts = [p.strip() for p in header.split("|")]
        name = re.sub(r"\s*\(.*?\)\s*$", "", parts[0]).strip()
        text = " ".join(lines)
        if not name or len(name.split()) > 5 or len(parts) < 2:
            return None
        if not self.job_ok(header + " " + text[:300], "remote" if re.search(r"\bremote\b", text[:500], re.I) and "no remote" not in text.lower() else ""):
            return None
        url = f"https://news.ycombinator.com/item?id={c['id']}"
        hrefs = [h for h in (a.attributes.get("href") for a in tree.css("a[href]")) if h and h.startswith("http")]
        site = next((h for h in hrefs if not any(s in h for s in SKIP_LINK)), None)
        email = next((e for e in EMAIL_RE.findall(text) if "example." not in e), None)
        people = [PersonRaw(full_name=f"{name} hiring team", source=self.name, title="Recruiter (hiring contact)", email=email.lower(), email_url=url)] if email else []
        return CompanyRaw(name=name, source=self.name, website=site, is_hiring=True, description=header[:300],
                          signals=[_job_signal(self.name, " | ".join(parts[1:4])[:140], "Remote", url)], people=people)


class RemoteOk(Source):
    name = "remoteok"
    seed = True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        data = self.client.get_json("https://remoteok.com/api") or []
        for j in data:
            if not isinstance(j, dict) or not j.get("company") or not j.get("position"):
                continue
            if not self.job_ok(f"{j['position']} {' '.join(j.get('tags') or [])}", j.get("location") or "", True):
                continue
            yield CompanyRaw(name=j["company"], source=self.name, is_hiring=True, description=(j.get("description") or "")[:300] or None,
                             signals=[_job_signal(self.name, j["position"], j.get("location") or "Remote", j.get("url") or j.get("apply_url"))])


class Remotive(Source):
    name = "remotive"
    seed = True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        term = re.sub(r"[^a-z0-9]", "", ((self.search.get("roles") or ["frontend"])[0]).lower())
        data = self.client.get_json(f"https://remotive.com/api/remote-jobs?category=software-dev&search={term}") or {}
        for j in data.get("jobs", []):
            if not self.job_ok(j.get("title", ""), j.get("candidate_required_location") or "", True):
                continue
            yield CompanyRaw(name=j["company_name"], source=self.name, is_hiring=True,
                             signals=[_job_signal(self.name, j["title"], j.get("candidate_required_location") or "Remote", j.get("url"))])


class WeWorkRemotely(Source):
    name = "weworkremotely"
    seed = True
    FEEDS = ["https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
             "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"]

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        for url in self.FEEDS:
            text = self.client.get_text(url, html=False)
            for e in feedparser.parse(text or "").entries:
                company, _, title = (e.get("title") or "").partition(":")
                if not title or not self.job_ok(title, "remote", True):
                    continue
                ts = e.get("published_parsed")
                yield CompanyRaw(name=company.strip(), source=self.name, is_hiring=True,
                                 signals=[_job_signal(self.name, title.strip(), "Remote", e.get("link"),
                                                      datetime.fromtimestamp(timegm(ts), UTC) if ts else None)])

