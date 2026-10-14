from collections.abc import Iterable
from typing import Any

from app.sources.base import CompanyRaw, Source

TICKERS = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


class SecEdgar(Source):
    """Tickers list, then submissions JSON per CIK filtered by SIC. The client User-Agent carries our contact
    string as SEC requires. SEC allows 10 req/s; we stay far below via the per-source rate limit."""

    name = "sec_edgar"
    requires_config = ["sic_codes"]
    seed = True

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        f = {**self.filters, **(query or {})}
        sics = {str(s) for s in f.get("sic_codes", [])}
        budget = int(f.get("max_companies", 50))
        tickers = self.client.get_json(TICKERS) or {}
        for row in tickers.values():
            if budget <= 0:
                break
            sub = self.client.get_json(SUBMISSIONS.format(cik=int(row["cik_str"])))
            budget -= 1
            if not sub or str(sub.get("sic")) not in sics:
                continue
            addr = (sub.get("addresses") or {}).get("business") or {}
            yield CompanyRaw(
                name=sub.get("name") or row["title"],
                source=self.name,
                website=sub.get("website") or None,
                industry=sub.get("sicDescription"),
                country=addr.get("stateOrCountryDescription"),
                city=addr.get("city"),
                extra={"cik": row["cik_str"], "ticker": row["ticker"], "sic": sub.get("sic")},
            )
