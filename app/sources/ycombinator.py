"""YC company directory.

ycombinator.com/companies renders client-side from an Algolia index that needs an app key embedded in the page,
so we do not call it. Default endpoint is the community-maintained static JSON mirror (yc-oss, GitHub Pages: free,
no key). Override with query_filters.endpoint to point at any compatible JSON list.
"""
import re
from collections.abc import Iterable
from typing import Any

from app.sources.base import CompanyRaw, Source

DEFAULT_ENDPOINT = "https://yc-oss.github.io/api/companies/all.json"


def expand_batch(b: str | None) -> str | None:
    """W24 -> Winter 2024 (the directory's own spelling); other values pass through."""
    m = re.fullmatch(r"([WSFX])(\d{2})", (b or "").strip(), re.I)
    if not m:
        return b
    return f"{ {'W': 'Winter', 'S': 'Summer', 'F': 'Fall', 'X': 'Spring'}[m[1].upper()] } 20{m[2]}"


class YCombinator(Source):
    name = "ycombinator"
    seed = True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        f = {**self.filters, **(query or {})}
        data = self.client.get_json(f.get("endpoint", DEFAULT_ENDPOINT)) or []
        want = f.get("batch")
        batches = {want, expand_batch(want)} if want else set()
        industry = (f.get("industry") or "").lower()
        for c in data:
            if batches and c.get("batch") not in batches:
                continue
            if industry and industry not in (c.get("industry") or "").lower():
                continue
            if f.get("hiring_only") and not c.get("isHiring"):
                continue
            loc = (c.get("all_locations") or "").split(",")
            yield CompanyRaw(
                name=c["name"],
                source=self.name,
                website=c.get("website"),
                stage=f"YC {c['batch']}" if c.get("batch") else None,
                industry=c.get("industry"),
                city=loc[0].strip() or None,
                country=loc[-1].strip() or None,
                employee_range=str(c["team_size"]) if c.get("team_size") else None,
                is_hiring=bool(c.get("isHiring")),
                description=c.get("one_liner"),
            )
