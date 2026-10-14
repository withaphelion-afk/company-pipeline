import dns.exception
import dns.resolver


def has_mx(domain: str) -> bool:
    """True if the domain has MX records. Patched in tests."""
    try:
        return len(dns.resolver.resolve(domain, "MX", lifetime=5)) > 0
    except (dns.exception.DNSException, OSError):
        return False


def mx_hosts(domain: str) -> list[str]:
    try:
        recs = sorted(dns.resolver.resolve(domain, "MX", lifetime=5), key=lambda r: r.preference)
        return [str(r.exchange).rstrip(".") for r in recs]
    except (dns.exception.DNSException, OSError):
        return []
