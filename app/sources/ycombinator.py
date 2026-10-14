"""YC company directory.

ycombinator.com/companies renders client-side from an Algolia index that needs an app key embedded in the page,
so we do not call it. Default endpoint is the community-maintained static JSON mirror (yc-oss, GitHub Pages: free,
no key). Override with query_filters.endpoint to point at any compatible JSON list.
"""
from collections.abc import Iterable
from typing import Any

from app.sources.base import CompanyRaw, Source

DEFAULT_ENDPOINT = "https://yc-oss.github.io/api/companies/all.json"


class YCombinator(Source):
    name = "ycombinator"
    seed = True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        f = {**self.filters, **(query or {})}
        data = self.client.get_json(f.get("endpoint", DEFAULT_ENDPOINT)) or []
        batch, industry = f.get("batch"), (f.get("industry") or "").lower()
        for c in data:
            if batch and c.get("batch") != batch:
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
