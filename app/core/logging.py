import json
import logging
from datetime import UTC, datetime

from app.core.config import get_settings

log = logging.getLogger("pipeline")
http_log = logging.getLogger("pipeline.http")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def log_request(source: str, url: str, status: int | str, cached: bool = False) -> None:
    """Every external request: source, URL, status, timestamp."""
    rec = {"ts": datetime.now(UTC).isoformat(), "source": source, "url": url, "status": status, "cached": cached}
    http_log.info(json.dumps(rec))
    try:
        d = get_settings().DATA_DIR
        d.mkdir(parents=True, exist_ok=True)
        with (d / "requests.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass
