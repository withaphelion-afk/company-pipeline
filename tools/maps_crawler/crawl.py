"""Google Maps crawler for the Maps Leads search queue (Playwright, headless Chromium).

Runs locally or on GitHub Actions. It takes searches from the app's queue, scrolls each results list, opens each business to read
its website, phone and listing links, and posts the leads to the app, which then runs the strict website check.

Rules built in: one search at a time, random pauses, a hard cap per run, and it NEVER solves or works around a CAPTCHA or
"unusual traffic" page: it stops the run and marks the search as errored. Only use it where you have the right to collect this data.

    python tools/maps_crawler/crawl.py --query "skin clinic in Saket, Delhi" --max-businesses 5 --dry-run   # local smoke test
    APP_URL=https://... INGEST_TOKEN=... python tools/maps_crawler/crawl.py                                 # work through the queue
"""
import argparse
import os
import random
import re
import sys
import time
from typing import Any
from urllib.parse import quote, urlparse

import httpx

CARD_JS = r"""() => {
  const feed = document.querySelector('div[role="feed"]');
  return [...feed.querySelectorAll('a.hfpxzc')].map((a) => {
    const card = a.closest('div[role="article"]') || a.parentElement;
    const lines = card.innerText.split('\n').map((s) => s.trim()).filter(Boolean);
    const rm = lines.map((l) => l.match(/^(\d\.\d)\((\d[\d,]*)\)$/)).find(Boolean);
    return { name: a.getAttribute('aria-label') || '', rating: rm ? `${rm[1]} stars ${rm[2]} Reviews` : '',
             category_address: lines.find((l) => l.includes('·')) || '', ad: /Sponsored/.test(card.innerText) };
  });
}"""
DETAIL_JS = r"""() => {
  const q = (s) => document.querySelector(s);
  const site = q('a[data-item-id="authority"]'), ph = q('button[data-item-id^="phone"]'), ad = q('button[data-item-id="address"]');
  const main = document.querySelector('div[role="main"]') || document;
  // only the listing's own info items (appointment, menu, booking...): the "web results" section links to OTHER businesses
  const links = [...new Set([...main.querySelectorAll('a[data-item-id][href^="http"]')].map((a) => a.href)
    .filter((h) => !/google\.|gstatic|goo\.gl|googleusercontent/.test(h)))].slice(0, 20);
  const h1 = [...document.querySelectorAll('h1')].map((h) => h.innerText.trim()).filter((x) => x && x !== 'Results').pop() || '';
  return { title: h1, website: site ? site.href : '', phone: ph ? (ph.getAttribute('aria-label') || '').replace(/^Phone:\s*/, '').trim() : '',
           address: ad ? (ad.getAttribute('aria-label') || '').replace(/^Address:\s*/, '') : '', links };
}"""


class Blocked(Exception):
    """Google showed a CAPTCHA / unusual-traffic page. We stop; we do not try to get past it."""


def search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/{quote(query)}?hl=en"


def is_blocked(url: str, text: str) -> bool:
    t = text.lower()
    return "/sorry/" in url or "unusual traffic" in t or "not a robot" in t or "captcha" in t


def shape_row(card: dict[str, Any], detail: dict[str, Any], maps_url: str) -> dict[str, Any]:
    """One lead as the app's /leads/ingest expects it."""
    cat = card.get("category_address", "")
    if detail.get("address") and "·" not in cat:
        cat = f"{cat} · {detail['address']}".strip(" ·")
    return {"name": card["name"], "rating": card.get("rating", ""), "category_address": cat, "phone": detail.get("phone", ""),
            "website": detail.get("website", ""), "links": detail.get("links", []), "detail_read": bool(detail.get("ok")), "maps_url": maps_url}


def batches(items: list[Any], n: int) -> list[list[Any]]:
    return [items[i:i + n] for i in range(0, len(items), n)]


class Api:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.h = {"X-Ingest-Token": token} if token else {}
        self.c = httpx.Client(timeout=90.0)  # a sleeping free server can take a minute to wake

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        for attempt in range(3):
            try:
                r = self.c.post(f"{self.base}{path}", json=json, headers=self.h)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))

    def claim(self) -> dict[str, Any] | None:
        return self._post("/leads/queue/next")["item"]  # type: ignore[no-any-return]

    def ingest(self, rows: list[dict[str, Any]], query: str) -> dict[str, int]:
        return self._post("/leads/ingest", {"rows": rows, "query": query})  # type: ignore[no-any-return]

    def done(self, qid: int, found: int, new: int, error: str | None) -> None:
        self._post(f"/leads/queue/{qid}/done", {"found": found, "new": new, "error": error})

    def verify(self) -> None:
        self._post("/control/jobs", {"stage": "verify_websites", "dry_run": False})


def pause(lo: float = 1.0, hi: float = 2.6) -> None:
    time.sleep(random.uniform(lo, hi))


def open_search(page: Any, query: str) -> None:
    page.goto(search_url(query), wait_until="domcontentloaded", timeout=45000)
    if "consent.google.com" in page.url:  # privacy-preserving choice on the cookie wall
        try:
            page.get_by_role("button", name=re.compile("reject all", re.I)).first.click(timeout=8000)
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
    try:
        page.wait_for_selector('div[role="feed"]', timeout=25000)
    except Exception as e:
        if is_blocked(page.url, page.inner_text("body")[:3000] if page.query_selector("body") else ""):
            raise Blocked("Google asked for verification (CAPTCHA / unusual traffic)") from e
        raise RuntimeError("no results list appeared (zero results, or the Maps layout changed)") from e


def scroll_all(page: Any, max_scrolls: int = 25) -> None:
    last = idle = 0
    for _ in range(max_scrolls):
        page.evaluate("document.querySelector('div[role=\"feed\"]').scrollTo(0, 1e9)")
        page.wait_for_timeout(int(random.uniform(1200, 2200)))
        n = page.locator("a.hfpxzc").count()
        idle = idle + 1 if n == last else 0
        last = n
        if idle >= 3 or page.locator("text=reached the end of the list").count():
            break


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def read_details(page: Any, idx: int, name: str, prev: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    """Open one business and read its panel. A read only counts when the panel's own title matches the business: Maps keeps the
    previous panel on screen for a moment, and reading it would give this business someone else's website."""
    want = norm(name)[:10]
    detail: dict[str, Any] = {"title": "", "website": "", "phone": "", "address": "", "links": [], "ok": False}
    url = ""
    for _attempt in range(2):  # one retry: open, read, go back, and try the business again
        page.evaluate("(i) => document.querySelectorAll('a.hfpxzc')[i].click()", idx)
        for _ in range(9):
            page.wait_for_timeout(900)
            d = page.evaluate(DETAIL_JS)
            if d["title"] and (norm(d["title"]).startswith(want) or want.startswith(norm(d["title"])[:10])):
                detail = {**d, "ok": True}
                break
        url = page.url.split("?")[0]
        back = page.locator('button[aria-label="Back"]').first
        if back.count():
            back.click()
        page.wait_for_selector('div[role="feed"]', timeout=15000)
        page.wait_for_timeout(700)
        if detail["ok"]:
            break
    return detail, url


def crawl_query(page: Any, api: Api | None, query: str, limit: int, deadline: float) -> tuple[int, int]:
    open_search(page, query)
    scroll_all(page)
    cards = [c for c in page.evaluate(CARD_JS) if c["name"] and not c["ad"]][:limit]
    print(f"  {len(cards)} businesses in the list for {query!r}")
    found = new = 0
    prev: dict[str, Any] | None = None
    pending: list[dict[str, Any]] = []
    for i, c in enumerate(cards):
        if time.time() > deadline:
            print("  time budget reached")
            break
        idx = next((k for k, x in enumerate(page.evaluate(CARD_JS)) if x["name"] == c["name"]), None)
        if idx is None:
            continue
        detail, url = read_details(page, idx, c["name"], prev)
        prev = detail
        if not detail["ok"]:
            print(f"  [{i + 1}/{len(cards)}] {c['name'][:40]}: panel never matched, left as 'not checked'")
        row = shape_row(c, detail, url)
        pending.append(row)
        found += 1
        print(f"  [{i + 1}/{len(cards)}] {c['name'][:40]:40} site={urlparse(detail['website']).netloc or 'no':28} phone={'yes' if detail['phone'] else 'no'} links={len(detail['links'])}")
        if len(pending) >= 15 or i == len(cards) - 1:
            if api:
                new += api.ingest(pending, query)["new"]
            pending = []
        pause()
    if pending and api:
        new += api.ingest(pending, query)["new"]
    return found, new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", help="crawl this one search instead of the queue (for example: skin clinic in Saket, Delhi)")
    ap.add_argument("--once", action="store_true", help="only one search from the queue")
    ap.add_argument("--max-businesses", type=int, default=int(os.getenv("MAX_BUSINESSES", "120")))
    ap.add_argument("--per-search", type=int, default=60)
    ap.add_argument("--max-minutes", type=int, default=int(os.getenv("MAX_MINUTES", "100")))
    ap.add_argument("--dry-run", action="store_true", help="read Maps but do not post anything to the app")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()
    api = None if a.dry_run else Api(os.environ["APP_URL"], os.getenv("INGEST_TOKEN", ""))
    from playwright.sync_api import sync_playwright

    deadline = time.time() + a.max_minutes * 60
    total = 0
    code = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not a.headed)
        page = browser.new_context(locale="en-IN", timezone_id="Asia/Kolkata", viewport={"width": 1366, "height": 900}).new_page()
        while total < a.max_businesses and time.time() < deadline:
            item = {"id": None, "query": a.query} if a.query else (api.claim() if api else None)
            if not item:
                print("nothing left in the queue")
                break
            print(f"search: {item['query']}")
            try:
                found, new = crawl_query(page, api, item["query"], min(a.per_search, a.max_businesses - total), deadline)
                total += found
                if api and item["id"]:
                    api.done(item["id"], found, new, None)
                print(f"  done: {found} read, {new} new")
            except Blocked as e:
                print(f"STOPPED: {e}. Not retrying or working around it.")
                if api and item["id"]:
                    api.done(item["id"], 0, 0, str(e))
                code = 2
                break
            except Exception as e:  # one bad search must not lose the rest of the run
                print(f"  error: {e}")
                if api and item["id"]:
                    api.done(item["id"], 0, 0, str(e)[:300])
            if a.once or a.query:
                break
            pause(4, 9)
        browser.close()
    if api and total and not os.getenv("NO_VERIFY"):
        api.verify()
        print("asked the app to run the strict website check")
    print(f"finished: {total} businesses read")
    return code


if __name__ == "__main__":
    sys.exit(main())
