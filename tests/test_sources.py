import httpx

from app.services.http_client import HttpClient, RateLimiter, RobotsDisallowed
from app.sources.company_site import CompanySite, extract_people
from app.sources.jobboards import Ashby, Greenhouse, Lever
from app.sources.press_rss import PressRss
from app.sources.sec_edgar import SecEdgar
from app.sources.ycombinator import YCombinator
from tests.conftest import fixture, make_transport


def mk(name, routes, **kw):
    return HttpClient(name, rate_limit=0, transport=make_transport(routes), backoff=0, **kw)


class Co:
    name = "Acme Robotics"
    normalized_name = "acme robotics"
    domain = "acme.com"
    extra = {"ats": "greenhouse", "slug": "acme"}


def test_greenhouse_companies_and_signals():
    routes = {"https://boards-api.greenhouse.io/v1/boards/acme": fixture("greenhouse_board.json"),
              "https://boards-api.greenhouse.io/v1/boards/acme/jobs": fixture("greenhouse_jobs.json")}
    src = Greenhouse(mk("greenhouse", routes), {"slugs": ["acme"]})
    (c,) = list(src.fetch_companies())
    assert c.name == "Acme Robotics" and c.is_hiring and c.extra["open_roles"] == 2
    (sig,) = list(src.fetch_signals(Co()))
    assert sig.type == "hiring" and "2 open roles" in sig.value


def test_lever_and_ashby():
    lv = Lever(mk("lever", {"https://api.lever.co/v0/postings/beta?mode=json": fixture("lever.json")}), {"slugs": ["beta"]})
    assert list(lv.fetch_companies())[0].name == "Beta"
    ab = Ashby(mk("ashby", {"https://api.ashbyhq.com/posting-api/job-board/gamma": fixture("ashby.json")}), {"slugs": ["gamma"]})
    assert list(ab.fetch_companies())[0].extra["open_roles"] == 1


def test_unavailable_board_is_skipped():
    assert list(Greenhouse(mk("greenhouse", {}), {"slugs": ["nope"]}).fetch_companies()) == []


def test_ycombinator_filters():
    routes = {"https://yc-oss.github.io/api/companies/all.json": fixture("yc.json")}
    src = YCombinator(mk("ycombinator", routes), {"batch": "W24"})
    (c,) = list(src.fetch_companies())
    assert c.name == "Delta Inc." and c.stage == "YC W24" and c.is_hiring and c.country == "USA"


def test_sec_edgar_sic_filter():
    routes = {"https://www.sec.gov/files/company_tickers.json": fixture("sec_tickers.json"),
              "https://data.sec.gov/submissions/CIK0000000001.json": fixture("sec_sub_1.json"),
              "https://data.sec.gov/submissions/CIK0000000002.json": fixture("sec_sub_2.json")}
    out = list(SecEdgar(mk("sec_edgar", routes), {"sic_codes": ["7374", 6199]}).fetch_companies())
    assert [c.name for c in out] == ["Alpha Software Corp"]


def test_extract_people_from_team_page():
    people = {p.full_name: p for p in extract_people(fixture("team.html"), "https://acme.com/team")}
    assert set(people) == {"Jane Founder", "Raj Patel", "Sam Builder"}
    assert people["Jane Founder"].email == "jane@acme.com"
    assert people["Raj Patel"].title == "Head of Talent" and people["Sam Builder"].title == "CTO"
    assert all(p.email != "ghost@example.com" for p in people.values())


def test_company_site_respects_robots_and_paths():
    routes = {"https://acme.com/robots.txt": "User-agent: *\nDisallow: /team\n",
              "https://acme.com/about": fixture("team.html")}
    src = CompanySite(mk("company_site", routes), {})
    assert {p.full_name for p in src.fetch_people(Co())} == {"Jane Founder", "Raj Patel", "Sam Builder"}
    # /team is disallowed, so only /about was fetched
    c = mk("company_site", routes)
    try:
        c.get("https://acme.com/team", html=True)
        raise AssertionError("expected RobotsDisallowed")
    except RobotsDisallowed:
        pass


def test_company_site_blog_signal():
    src = CompanySite(mk("company_site", {"https://acme.com/blog": fixture("blog.html")}), {})
    (sig,) = list(src.fetch_signals(Co()))
    assert sig.type == "post" and sig.url == "https://acme.com/blog/shipping-v2-today"


def test_press_rss_matches_funding_and_launch():
    src = PressRss(mk("press_rss", {"https://f.example/feed": fixture("feed.xml")}), {"feeds": ["https://f.example/feed"]})
    sigs = {s.type: s for s in src.fetch_signals(Co())}
    assert set(sigs) == {"funding", "launch"}
    assert sigs["funding"].url == "https://news.example/acme-seed" and sigs["funding"].observed_at.year == 2025


def test_retry_on_5xx_then_success():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503 if len(calls) < 3 else 200, text="{}")
    c = HttpClient("t", rate_limit=0, transport=httpx.MockTransport(handler), backoff=0)
    assert c.get("https://x.test/a").status_code == 200 and len(calls) == 3


def test_no_retry_on_404():
    calls = []
    c = HttpClient("t", rate_limit=0, backoff=0,
                   transport=httpx.MockTransport(lambda r: (calls.append(1), httpx.Response(404))[1]))
    assert c.get("https://x.test/a").status_code == 404 and len(calls) == 1


def test_cache_replay_and_user_agent(tmp_path):
    seen = {}

    def handler(req):
        seen["ua"] = req.headers["user-agent"]
        return httpx.Response(200, text='{"a": 1}')
    live = HttpClient("t", rate_limit=0, transport=httpx.MockTransport(handler), data_dir=tmp_path)
    assert live.get_json("https://x.test/j") == {"a": 1}
    assert seen["ua"] == "CompanyPipeline/0.1 (+contact: test@example.com)"
    replay = HttpClient("t", rate_limit=0, from_cache=True, data_dir=tmp_path,
                        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError("network used"))))
    assert replay.get_json("https://x.test/j") == {"a": 1}
    assert replay.get_json("https://x.test/other") is None


def test_rate_limiter_spaces_requests():
    t = [0.0]
    slept = []
    rl = RateLimiter(clock=lambda: t[0], sleep=lambda d: (slept.append(d), t.__setitem__(0, t[0] + d)))
    rl.wait("h", 2)
    rl.wait("h", 2)
    rl.wait("other", 2)
    assert slept == [2.0]


def test_press_rss_investor_firms_become_companies():
    from app.sources.press_rss import investor_names
    assert investor_names("Acme raises $5M seed led by Sequoia Capital and Accel, with participation from Peak XV.") == ["Sequoia Capital", "Accel", "Peak XV"]
    assert investor_names("Round led by existing investors.") == []
    feed = '<rss version="2.0"><channel><title>t</title><item><title>Beta raises $9M Series A led by Matrix Partners</title><link>https://n/b</link></item></channel></rss>'
    src = PressRss(mk("press_rss", {"https://f.example/f": feed}), {"feeds": ["https://f.example/f"]})
    (c,) = list(src.fetch_companies())
    assert c.name == "Matrix Partners" and c.extra["kind"] == "investor"


def test_yc_batch_alias():
    from app.sources.ycombinator import expand_batch
    assert [expand_batch(x) for x in ("W24", "s23", "Fall 2024", None)] == ["Winter 2024", "Summer 2023", "Fall 2024", None]
