from app.sources.base import Source
from app.sources.company_site import CompanySite
from app.sources.jobboards import Ashby, Greenhouse, Lever
from app.sources.mca21 import Mca21
from app.sources.press_rss import PressRss
from app.sources.remote_jobs import HnHiring, RemoteOk, Remotive, WeWorkRemotely
from app.sources.sec_edgar import SecEdgar
from app.sources.ycombinator import YCombinator

REGISTRY: dict[str, type[Source]] = {
    c.name: c for c in (YCombinator, Greenhouse, Lever, Ashby, HnHiring, RemoteOk, Remotive, WeWorkRemotely, Mca21, SecEdgar,
                        CompanySite, PressRss)
}
# What "enable recommended" turns on: every source that needs no config, plus starter boards for the ATS sources.
STARTER_FILTERS: dict[str, dict] = {  # type: ignore[type-arg]
    "greenhouse": {"slugs": ["stripe", "airbnb", "figma", "discord", "databricks", "cloudflare", "coinbase", "reddit", "robinhood",
                             "instacart", "dropbox", "asana", "gitlab", "mongodb", "twilio", "datadog", "okta", "pinterest",
                             "lyft", "doordash", "brex", "gusto"]},
    "lever": {"slugs": ["spotify", "palantir", "plaid", "netlify"]},
    "ashby": {"slugs": ["ramp", "notion", "linear", "openai", "retool", "deel"]},
    "sec_edgar": {"sic_codes": [7372, 7374, 6199, 6282], "max_companies": 30},
}
RECOMMENDED = ["ycombinator", "hn_hiring", "remoteok", "remotive", "weworkremotely", "press_rss", *STARTER_FILTERS]
SEED_SOURCES = [n for n, c in REGISTRY.items() if c.seed]
SIGNAL_SOURCES = ["greenhouse", "lever", "ashby", "press_rss"]
