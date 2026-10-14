"""Greenhouse, Lever and Ashby public job-board APIs (no auth, JSON)."""
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from app.sources.base import CompanyLike, CompanyRaw, SignalRaw, Source


class JobBoardSource(Source):
    requires_config = ["slugs"]
    seed = True
    board_url = ""  # human-facing URL template with {slug}

    def _board(self, slug: str) -> tuple[str, list[dict[str, str]]] | None:
        """Return (company name, [{title, location, url}]) or None if the board is unavailable."""
        raise NotImplementedError

    def fetch_companies(self, query: dict[str, Any] | None = None) -> Iterable[CompanyRaw]:
        for slug in self.filters.get("slugs", []):
            board = self._board(slug)
            if board is None:
                continue
            name, jobs = board
            yield CompanyRaw(
                name=name,
                source=self.name,
                is_hiring=bool(jobs),
                city=jobs[0]["location"] if jobs else None,
                extra={"ats": self.name, "slug": slug, "open_roles": len(jobs)},
            )

    def fetch_signals(self, company: CompanyLike) -> Iterable[SignalRaw]:
        if company.extra.get("ats") != self.name:
            return
        slug = company.extra["slug"]
        board = self._board(slug)
        if board and board[1]:
            jobs = board[1]
            titles = ", ".join(j["title"] for j in jobs[:3])
            yield SignalRaw(
                "hiring",
                f"{len(jobs)} open roles, including {titles}",
                self.name,
                self.board_url.format(slug=slug),
                datetime.now(UTC),
            )


class Greenhouse(JobBoardSource):
    name = "greenhouse"
    board_url = "https://boards.greenhouse.io/{slug}"

    def _board(self, slug: str) -> tuple[str, list[dict[str, str]]] | None:
        base = f"https://boards-api.greenhouse.io/v1/boards/{slug}"
        info = self.client.get_json(base)
        data = self.client.get_json(f"{base}/jobs")
        if info is None or data is None:
            return None
        jobs = [
            {"title": j["title"], "location": (j.get("location") or {}).get("name", ""), "url": j.get("absolute_url", "")}
            for j in data.get("jobs", [])
        ]
        return info.get("name", slug), jobs


class Lever(JobBoardSource):
    name = "lever"
    board_url = "https://jobs.lever.co/{slug}"

    def _board(self, slug: str) -> tuple[str, list[dict[str, str]]] | None:
        data = self.client.get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        if data is None:
            return None
        jobs = [
            {"title": j["text"], "location": (j.get("categories") or {}).get("location", ""), "url": j.get("hostedUrl", "")}
            for j in data
        ]
        return slug.replace("-", " ").title(), jobs


class Ashby(JobBoardSource):
    name = "ashby"
    board_url = "https://jobs.ashbyhq.com/{slug}"

    def _board(self, slug: str) -> tuple[str, list[dict[str, str]]] | None:
        data = self.client.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        if data is None:
            return None
        jobs = [
            {"title": j["title"], "location": j.get("location", ""), "url": j.get("jobUrl", "")}
            for j in data.get("jobs", [])
        ]
        return slug.replace("-", " ").title(), jobs
