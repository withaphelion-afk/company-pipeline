from collections.abc import Callable

from app.stages import (
    discover,
    draft,
    enrich,
    find_contacts,
    rank,
    resolve_domains,
    verify_email,
    verify_websites,
)
from app.stages.base import StageContext

STAGES: dict[str, Callable[[StageContext], None]] = {
    "discover": discover.run,
    "resolve_domains": resolve_domains.run,
    "find_contacts": find_contacts.run,
    "verify_email": verify_email.run,
    "enrich": enrich.run,
    "rank": rank.run,
    "draft": draft.run,
    "verify_websites": verify_websites.run,
}
