"""Strict "does this business have a website?" check for Maps leads.

Statuses: has_site (listed on Maps, or a link/domain whose page matches the business), probable_site (the listing links to a
site we could not match), none (details were read and nothing was found), unknown (details were never read).
"""
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from app.services.http_client import HttpClient

AGGREGATORS = (
    "google.", "goo.gl", "facebook.", "fb.com", "instagram.", "twitter.", "x.com", "linkedin.", "youtube.", "youtu.be", "justdial.",
    "practo.", "sulekha.", "indiamart.", "tripadvisor.", "zomato.", "swiggy.", "lybrate.", "linktr.ee", "wa.me", "whatsapp.", "bit.ly",
    "wikipedia.", "yelp.", "pinterest.", "tiktok.", "apple.com", "booking.com", "magicpin.", "nearbuy.", "urbancompany.",
)
GENERIC = {
    "clinic", "clinics", "centre", "center", "hospital", "dental", "dentist", "skin", "care", "studio", "salon", "hair", "laser",
    "aesthetic", "aesthetics", "cosmetic", "health", "medical", "the", "and", "best", "doctor", "specialist", "institute", "services",
    "service", "delhi", "new", "pvt", "ltd", "multispeciality", "super", "speciality", "wellness", "polyclinic", "dermatology",
}
TLDS = (".com", ".in", ".co.in", ".clinic", ".org")


@dataclass
class Verdict:
    status: str  # has_site | probable_site | none | unknown
    url: str | None
    evidence: str


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_aggregator(url: str) -> bool:
    h = host_of(url)
    return not h or any(a in h for a in AGGREGATORS)


def clean_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/") if p.scheme else url


def origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def distinctive_tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", name.lower())
    return [w for w in words if w not in GENERIC and not w.isdigit()][:3]


def domain_guesses(name: str) -> list[str]:
    toks = distinctive_tokens(name)
    allw = re.findall(r"[a-z0-9]{2,}", name.lower())
    slugs = []
    if toks:
        slugs += ["".join(toks), "-".join(toks)]
    if allw:
        slugs.append("".join(allw[:4]))
    out: list[str] = []
    for s in dict.fromkeys(slugs):
        out += [f"{s}{t}" for t in TLDS]
    return out[:10]


def resolves(host: str) -> bool:
    try:
        socket.gethostbyname(host)
        return True
    except OSError:
        return False


def page_matches(html: str, name: str, phone: str, strict: bool = False) -> str | None:
    """Does this page belong to the business? Phone digits first, then every distinctive word of the name.
    strict (domain guesses): a single distinctive word is not enough, since many unrelated sites contain it."""
    text = LexborHTMLParser(html[:300_000]).text(separator=" ").lower() if html else ""
    digits = re.sub(r"\D", "", phone)[-8:]
    if len(digits) >= 8 and digits in re.sub(r"\D", "", text):
        return "phone number"
    toks = distinctive_tokens(name)
    if toks and (len(toks) >= 2 or not strict) and all(t in text for t in toks):
        return "business name"
    return None


def _fetch(client: HttpClient, url: str) -> str | None:
    try:
        return client.get_text(url, html=True)
    except httpx.HTTPError:
        return None


def classify(name: str, phone: str, maps_website: str, links: list[str], detail_read: bool, client: HttpClient) -> Verdict:
    if maps_website and not is_aggregator(maps_website):
        return Verdict("has_site", clean_url(maps_website), "listed on Google Maps")
    seen: set[str] = set()
    cands: list[tuple[str, str]] = []
    for u in links:
        if u.startswith("http") and not is_aggregator(u) and host_of(u) not in seen:
            seen.add(host_of(u))
            cands.append((origin(u), "link on the listing"))  # the homepage says who the business is, not a deep /book page
    for d in domain_guesses(name):
        if d not in seen and resolves(d):
            seen.add(d)
            cands.append((f"https://{d}", "domain guess"))
    unverified: list[str] = []
    for url, why in cands:
        html = _fetch(client, url)
        match = page_matches(html, name, phone, strict=why == "domain guess") if html else None
        if match:
            return Verdict("has_site", url, f"{why}; the page matches the {match}")
        if why == "link on the listing":
            unverified.append(url)
    if unverified:
        return Verdict("probable_site", unverified[0], "the listing links to a site that could not be matched to this business")
    if detail_read:
        return Verdict("none", None, "no website on Maps, no site links on the listing, no matching domain")
    return Verdict("unknown", None, "business details were not read")
