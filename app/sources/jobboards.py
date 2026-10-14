"""Greenhouse, Lever and Ashby public job-board APIs (no auth, JSON). Only jobs matching the saved search count."""
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from app.sources.base import CompanyLike, CompanyRaw, SignalRaw, Source

Job = dict[str, Any]  # title, location, url, remote


class JobBoardSource(Source):
    requires_config = ["slugs"]
    seed = True
    board_url = ""  # human-facing URL template with {slug}

    def _board(self, slug: str) -> tuple[str, list[Job]] | None:
        """Return (company name, jobs) or None if the board is unavailable."""
        raise NotImplementedError

    def _matches(self, jobs: list[Job]) -> list[Job]:
        return [j for j in jobs if self.job_ok(j["title"], j.get("location", ""), j.get("remote"))]

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        for slug in self.filters.get("slugs", []):
            board = self._board(slug)
            if board is None:
                continue
            name, jobs = board
            hits = self._matches(jobs)
            yield CompanyRaw(
                name=name,
                source=self.name,
                is_hiring=bool(hits),
                city=jobs[0].get("location") if jobs else None,
                extra={"ats": self.name, "slug": slug, "open_roles": len(jobs), "matching_roles": len(hits)},
                signals=[self._signal(j) for j in hits[:5]],
            )

    def _signal(self, j: Job) -> SignalRaw:
        return SignalRaw("hiring", f"Job: {j['title']} ({j.get('location') or 'Remote'})", self.name, j.get("url") or None,
                         datetime.now(UTC))

    def fetch_signals(self, company: CompanyLike) -> Iterable[SignalRaw]:
        if company.extra.get("ats") != self.name:
            return
        board = self._board(company.extra["slug"])
        for j in (self._matches(board[1]) if board else [])[:5]:
            yield self._signal(j)


class Greenhouse(JobBoardSource):
    name = "greenhouse"
    board_url = "https://boards.greenhouse.io/{slug}"

    def _board(self, slug: str) -> tuple[str, list[Job]] | None:
        base = f"https://boards-api.greenhouse.io/v1/boards/{slug}"
        info = self.client.get_json(base)
        data = self.client.get_json(f"{base}/jobs")
        if info is None or data is None:
            return None
        jobs = [{"title": j["title"], "location": (j.get("location") or {}).get("name", ""), "url": j.get("absolute_url", "")}
                for j in data.get("jobs", [])]
        return info.get("name", slug), jobs


class Lever(JobBoardSource):
    name = "lever"
    board_url = "https://jobs.lever.co/{slug}"

    def _board(self, slug: str) -> tuple[str, list[Job]] | None:
        data = self.client.get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        if data is None:
            return None
        jobs = [{"title": j["text"], "location": (j.get("categories") or {}).get("location", ""), "url": j.get("hostedUrl", ""),
                 "remote": j.get("workplaceType") == "remote"} for j in data]
        return slug.replace("-", " ").title(), jobs


class Ashby(JobBoardSource):
    name = "ashby"
    board_url = "https://jobs.ashbyhq.com/{slug}"

    def _board(self, slug: str) -> tuple[str, list[Job]] | None:
        data = self.client.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        if data is None:
            return None
        jobs = [{"title": j["title"], "location": j.get("location", ""), "url": j.get("jobUrl", ""),
                 "remote": bool(j.get("isRemote")) or j.get("workplaceType") == "Remote"} for j in data.get("jobs", [])]
        return slug.replace("-", " ").title(), jobs
