from app.sources.base import Source


class Mca21(Source):
    """Stub. TODO: MCA21 (India's Ministry of Corporate Affairs registry) has no public API; company master data
    needs a licensed provider or an official bulk dataset. Until one is chosen (ask first if it needs an account or
    key) this adapter returns nothing and cannot be enabled."""

    name = "mca21"
    is_stub = True
