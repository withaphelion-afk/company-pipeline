from app.sources.base import Source
from app.sources.company_site import CompanySite
from app.sources.jobboards import Ashby, Greenhouse, Lever
from app.sources.mca21 import Mca21
from app.sources.press_rss import PressRss
from app.sources.sec_edgar import SecEdgar
from app.sources.ycombinator import YCombinator

REGISTRY: dict[str, type[Source]] = {
    c.name: c for c in (YCombinator, Greenhouse, Lever, Ashby, Mca21, SecEdgar, CompanySite, PressRss)
}
SEED_SOURCES = [n for n, c in REGISTRY.items() if c.seed]
SIGNAL_SOURCES = ["greenhouse", "lever", "ashby", "press_rss"]
