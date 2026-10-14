import re
from calendar import timegm
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import feedparser

from app.services.normalize import normalize_name
from app.sources.base import CompanyLike, SignalRaw, Source

DEFAULT_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://entrackr.com/feed",
    "https://inc42.com/feed/",
    "https://economictimes.indiatimes.com/small-biz/startups/rssfeeds/11993118.cms",  # verify URL before relying on it
    "https://news.crunchbase.com/feed/",
]
FUNDING_RE = re.compile(r"\b(raises?|raised|funding|seed|series [a-z]|secures?|bags?)\b", re.I)
LAUNCH_RE = re.compile(r"\b(launch(es|ed)?|unveils?|introduces?|rolls? out|releases?)\b", re.I)


class PressRss(Source):
    name = "press_rss"

    def __init__(self, *a: Any, **kw: Any):
        super().__init__(*a, **kw)
        self._items: list[tuple[str, str, str, datetime | None]] | None = None  # (norm title, title, link, date)

    def _load(self) -> list[tuple[str, str, str, datetime | None]]:
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
                    self._items.append((f" {normalize_name(t)} ", t, e.get("link", ""), when))
        return self._items

    def fetch_signals(self, company: CompanyLike) -> Iterable[SignalRaw]:
        needle = f" {company.normalized_name} "
        if len(company.normalized_name) < 3:
            return
        for norm, title, link, when in self._load():
            if needle not in norm:
                continue
            kind = "funding" if FUNDING_RE.search(title) else "launch" if LAUNCH_RE.search(title) else None
            if kind:
                yield SignalRaw(kind, title, self.name, link, when)
