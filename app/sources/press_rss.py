import re
from calendar import timegm
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, NamedTuple

import feedparser

from app.services.normalize import normalize_name
from app.sources.base import CompanyLike, CompanyRaw, SignalRaw, Source

DEFAULT_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://entrackr.com/feed",
    "https://inc42.com/feed/",
    "https://economictimes.indiatimes.com/small-biz/startups/rssfeeds/11993118.cms",  # verify URL before relying on it
    "https://news.crunchbase.com/feed/",
]
FUNDING_RE = re.compile(r"\b(raises?|raised|funding|seed|series [a-z]|secures?|bags?)\b", re.I)
LAUNCH_RE = re.compile(r"\b(launch(es|ed)?|unveils?|introduces?|rolls? out|releases?)\b", re.I)
# "... led by Sequoia Capital and Accel", "backed by A, B", "investors including X, Y"
INVESTOR_RE = re.compile(r"(?:led by|backed by|investors? (?:include|including)|participation from)\s+([^.;:()—]+)", re.I)
NOT_INVESTORS = {"existing", "others", "other", "new", "several", "angel", "angels", "investors", "participation", "the", "a"}
TAG_RE = re.compile(r"<[^>]+>")


class Item(NamedTuple):
    norm_title: str
    title: str
    link: str
    when: datetime | None
    text: str  # title + summary, tags stripped


def investor_names(text: str) -> list[str]:
    """Firm names from 'led by X and Y' style phrases: 1-4 capitalised words each."""
    out: list[str] = []
    for m in INVESTOR_RE.finditer(text):
        for part in re.split(r",| and | & |\bwith\b|\bat\b|\bfor\b", m[1]):
            name = re.sub(r"^(participation )?from\s+", "", part.strip(" '\""), flags=re.I)
            words = name.split()
            if 1 <= len(words) <= 4 and all(w[0].isupper() or w[0].isdigit() for w in words) and name.lower() not in NOT_INVESTORS:
                out.append(name)
    return out


class PressRss(Source):
    name = "press_rss"
    seed = True  # discover also turns investor firms named in funding news into companies (kind=investor)

    def __init__(self, *a: Any, **kw: Any):
        super().__init__(*a, **kw)
        self._items: list[Item] | None = None

    def _load(self) -> list[Item]:
        if self._items is None:
            self._items = []
            for url in self.filters.get("feeds") or DEFAULT_FEEDS:
                text = self.client.get_text(url, html=False)  # RSS is not an HTML page: no robots gate
                if not text:
                    continue
                for e in feedparser.parse(text).entries:
                    t = e.get("title", "")
                    ts = e.get("published_parsed") or e.get("updated_parsed")
                    when = datetime.fromtimestamp(timegm(ts), UTC) if ts else None
                    body = TAG_RE.sub(" ", e.get("summary", ""))
                    self._items.append(Item(f" {normalize_name(t)} ", t, e.get("link", ""), when, f"{t}. {body}"))
        return self._items

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        seen: set[str] = set()
        for it in self._load():
            if not FUNDING_RE.search(it.title):
                continue
            for name in investor_names(it.text):
                key = normalize_name(name)
                if key and key not in seen:
                    seen.add(key)
                    yield CompanyRaw(name=name, source=self.name, industry="Venture capital",
                                     description=f"Investor named in: {it.title}", extra={"kind": "investor", "evidence": it.link})

    def fetch_signals(self, company: CompanyLike) -> Iterable[SignalRaw]:
        needle = f" {company.normalized_name} "
        if len(company.normalized_name) < 3:
            return
        for it in self._load():
            if needle not in it.norm_title:
                continue
            kind = "funding" if FUNDING_RE.search(it.title) else "launch" if LAUNCH_RE.search(it.title) else None
            if kind:
                yield SignalRaw(kind, it.title, self.name, it.link, it.when)
