"""Single HTTP entry point: robots.txt, per-domain rate limit, retries, raw cache, request log."""
import hashlib
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import robotparser
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import log_request


class RobotsDisallowed(Exception):
    pass


class RateLimiter:
    """Minimum interval between requests per host (thread-safe)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._clock, self._sleep = clock, sleep

    def wait(self, host: str, interval: float) -> None:
        if interval <= 0:
            return
        with self._lock:
            delay = self._last.get(host, -1e9) + interval - self._clock()
            if delay > 0:
                self._sleep(delay)
            self._last[host] = self._clock()


_limiter = RateLimiter()
_robots: dict[str, robotparser.RobotFileParser | None] = {}


def clear_robots_cache() -> None:
    _robots.clear()


class HttpClient:
    def __init__(
        self,
        source: str,
        rate_limit: float | None = None,
        from_cache: bool = False,
        transport: httpx.BaseTransport | None = None,
        limiter: RateLimiter | None = None,
        backoff: float = 1.0,
        data_dir: Path | None = None,
    ):
        s = get_settings()
        self.source = source
        self.rate = s.DEFAULT_RATE_LIMIT_SECONDS if rate_limit is None else rate_limit
        self.from_cache = from_cache
        self.limiter = limiter or _limiter
        self.backoff = backoff
        self.data_dir = data_dir or s.DATA_DIR
        self.ua = s.user_agent
        self._client = httpx.Client(
            timeout=10.0, transport=transport, headers={"User-Agent": self.ua}, follow_redirects=True
        )

    # --- cache -------------------------------------------------------
    def _key(self, url: str) -> str:
        return hashlib.sha1(url.encode()).hexdigest() + ".json"

    def _cache_write(self, url: str, status: int, text: str) -> None:
        d = self.data_dir / "raw" / self.source / datetime.now(UTC).strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        (d / self._key(url)).write_text(json.dumps({"url": url, "status": status, "text": text}), encoding="utf-8")

    def _cache_read(self, url: str) -> tuple[int, str] | None:
        root = self.data_dir / "raw" / self.source
        for day in sorted(root.glob("*"), reverse=True) if root.exists() else []:
            f = day / self._key(url)
            if f.exists():
                j = json.loads(f.read_text(encoding="utf-8"))
                return j["status"], j["text"]
        return None

    # --- robots ------------------------------------------------------
    def _robots_for(self, url: str) -> robotparser.RobotFileParser | None:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in _robots:
            rp = robotparser.RobotFileParser()
            try:
                self.limiter.wait(p.netloc, self.rate)
                r = self._client.get(f"{base}/robots.txt")
                log_request(self.source, f"{base}/robots.txt", r.status_code)
                if r.status_code in (401, 403):
                    rp.disallow_all = True  # type: ignore[attr-defined]
                elif r.status_code >= 400:
                    rp.allow_all = True  # type: ignore[attr-defined]
                else:
                    rp.parse(r.text.splitlines())
                _robots[base] = rp
            except httpx.HTTPError:
                _robots[base] = None  # robots.txt unreachable: treated as allow, cached for the process
        return _robots[base]

    def _check_robots(self, url: str) -> float:
        rp = self._robots_for(url)
        if rp is None:
            return 0.0
        if not rp.can_fetch(self.ua, url):
            raise RobotsDisallowed(url)
        return float(rp.crawl_delay(self.ua) or 0)

    # --- fetch -------------------------------------------------------
    def get(self, url: str, *, html: bool = False, **kw: Any) -> httpx.Response | None:
        """GET with retries. None on cache miss in from_cache mode. Raises RobotsDisallowed for html."""
        if self.from_cache:
            hit = self._cache_read(url)
            if hit is None:
                return None
            log_request(self.source, url, hit[0], cached=True)
            return httpx.Response(hit[0], text=hit[1], request=httpx.Request("GET", url))
        crawl_delay = self._check_robots(url) if html else 0.0
        host = urlparse(url).netloc
        resp: httpx.Response | None = None
        for attempt in range(4):
            self.limiter.wait(host, max(self.rate, crawl_delay))
            try:
                resp = self._client.get(url, **kw)
            except httpx.HTTPError:
                if attempt == 3:
                    log_request(self.source, url, "error")
                    raise
                time.sleep(self.backoff * 2**attempt)
                continue
            log_request(self.source, url, resp.status_code)
            if (resp.status_code == 429 or resp.status_code >= 500) and attempt < 3:
                time.sleep(self.backoff * 2**attempt)
                continue
            break
        assert resp is not None
        if resp.status_code < 400:
            self._cache_write(url, resp.status_code, resp.text)
        return resp

    def get_json(self, url: str, **kw: Any) -> Any | None:
        r = self.get(url, **kw)
        if r is None or r.status_code >= 400:
            return None
        return r.json()

    def get_text(self, url: str, *, html: bool = True) -> str | None:
        try:
            r = self.get(url, html=html)
        except RobotsDisallowed:
            return None
        return r.text if r is not None and r.status_code < 400 else None

    def head_ok(self, url: str) -> bool:
        """Reachability check (HEAD). Not cached; always False in from_cache mode."""
        if self.from_cache:
            return False
        try:
            self.limiter.wait(urlparse(url).netloc, self.rate)
            r = self._client.head(url)
            log_request(self.source, url, r.status_code)
            return r.status_code < 500
        except httpx.HTTPError:
            log_request(self.source, url, "error")
            return False
