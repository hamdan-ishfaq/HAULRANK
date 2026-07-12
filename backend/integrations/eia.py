"""EIA diesel — cache with fallback."""

from __future__ import annotations

import httpx
from django.conf import settings
from django.core.cache import cache

CACHE_KEY = "eia:diesel:usd_per_gal"
CACHE_TTL = 60 * 60 * 24 * 7


def get_diesel_usd_per_gal() -> float:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return float(cached)

    key = getattr(settings, "EIA_API_KEY", "") or ""
    if not key:
        # ponytail: no EIA key → fixed fallback; upgrade: set EIA_API_KEY
        return float(settings.FALLBACK_DIESEL_USD_PER_GAL)

    url = (
        "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
        f"?api_key={key}&frequency=weekly"
        "&data[0]=value&facets[product][]=EPD2D"
        "&sort[0][column]=period&sort[0][direction]=desc&length=1"
    )
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            rows = resp.json().get("response", {}).get("data", [])
            value = float(rows[0]["value"]) if rows else None
    except Exception:
        # ponytail: EIA down → fallback; upgrade: retry/backoff
        return float(settings.FALLBACK_DIESEL_USD_PER_GAL)

    if value is None:
        return float(settings.FALLBACK_DIESEL_USD_PER_GAL)

    cache.set(CACHE_KEY, value, CACHE_TTL)
    return value
