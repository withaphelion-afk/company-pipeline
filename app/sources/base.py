import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.services.http_client import HttpClient

DEFAULT_SEARCH: dict[str, Any] = {"roles": ["frontend", "front-end", "front end", "react", "ui engineer"], "remote_only": True,
                                  "goals": ["hire", "invest", "advise"]}


@dataclass
class SignalRaw:
    type: str
    value: str
    source: str
    url: str | None = None
    observed_at: datetime | None = None


@dataclass
class PersonRaw:
    full_name: str
    source: str
    title: str | None = None
    email: str | None = None  # address published on a page
    email_url: str | None = None
    linkedin_url: str | None = None  # only if the page itself links it; never scraped from LinkedIn
    twitter_url: str | None = None
    github_url: str | None = None


@dataclass
class CompanyRaw:
    name: str
    source: str
    website: str | None = None
    stage: str | None = None
    industry: str | None = None
    country: str | None = None
    city: str | None = None
    employee_range: str | None = None
    is_hiring: bool = False
    description: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    signals: list[SignalRaw] = field(default_factory=list)  # e.g. the matching job post
    people: list[PersonRaw] = field(default_factory=list)  # e.g. a contact printed in the post


class CompanyLike(Protocol):
    name: str
    normalized_name: str
    domain: str | None
    extra: dict[str, Any]


class Source:
    name = ""
    requires_config: list[str] = []  # keys that must be present in query_filters before enabling
    is_stub = False
    seed = False  # used by the discover stage

    def __init__(self, client: HttpClient, filters: dict[str, Any] | None = None):
        self.client = client
        self.filters = filters or {}
        self.search: dict[str, Any] = DEFAULT_SEARCH  # set by the stage from the saved Search settings

    def job_ok(self, title: str, location: str = "", remote: bool | None = None) -> bool:
        """Does a job match the saved search: a role keyword in the title and (if required) remote."""
        t = title.lower()
        roles = [r.lower() for r in self.search.get("roles") or []]
        if roles and not any(re.search(rf"\b{re.escape(r)}\b", t) for r in roles):
            return False
        if self.search.get("remote_only", True):
            loc = (location or "").lower()
            return bool(remote or "remote" in loc or "remote" in t or "anywhere" in loc or "worldwide" in loc)
        return True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        return []

    def fetch_people(self, company: CompanyLike) -> Iterable[PersonRaw]:
        return []

    def fetch_signals(self, company: CompanyLike) -> Iterable[SignalRaw]:
        return []

    @classmethod
    def missing_config(cls, filters: dict[str, Any]) -> list[str]:
        return [k for k in cls.requires_config if not filters.get(k)]
