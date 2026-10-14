"""Optional RCPT TO probe. Never sends a message (no DATA). Off by default; allowlisted domains only."""
import secrets
import smtplib
import time

from app.core.config import get_settings
from app.services.dns_tools import mx_hosts

PROBE_INTERVAL = 3.0
_last_probe = 0.0


def probe_allowed(domain: str) -> bool:
    s = get_settings()
    return s.SMTP_PROBE_ENABLED and domain.lower() in s.smtp_domains


def _rcpt(host: str, address: str, timeout: float) -> int | None:
    global _last_probe
    time.sleep(max(0.0, _last_probe + PROBE_INTERVAL - time.monotonic()))
    _last_probe = time.monotonic()
    sender = "probe@" + get_settings().CONTACT_EMAIL.split("@")[-1]
    try:
        with smtplib.SMTP(host, 25, timeout=timeout) as s:
            s.ehlo_or_helo_if_needed()
            s.mail(sender)
            code, _ = s.rcpt(address)
            s.rset()
            return code
    except (smtplib.SMTPException, OSError):
        return None


def check_address(address: str, timeout: float = 8.0) -> str:
    """Return valid | invalid | catch_all | unknown. Tests a random address first to detect catch-all."""
    domain = address.rsplit("@", 1)[1]
    hosts = mx_hosts(domain)
    if not hosts:
        return "unknown"
    host = hosts[0]
    rand = _rcpt(host, f"{secrets.token_hex(8)}@{domain}", timeout)
    if rand is None:
        return "unknown"
    if 200 <= rand < 300:
        return "catch_all"
    code = _rcpt(host, address, timeout)
    if code is None:
        return "unknown"
    if 200 <= code < 300:
        return "valid"
    return "invalid" if 500 <= code < 600 else "unknown"
