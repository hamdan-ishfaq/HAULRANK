"""OpenWeatherMap risk for route midpoint — fail open if unavailable."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from django.conf import settings
from django.core.cache import cache

CACHE_TTL = 60 * 60 * 3

# Weather condition ids that imply disruption (OWM)
SEVERE_IDS = {
    202,
    212,
    221,
    230,
    231,
    232,  # thunderstorm
    502,
    503,
    504,
    511,
    522,
    531,  # heavy rain
    602,
    622,
    616,  # snow
    771,
    781,  # squall / tornado
}


@dataclass(frozen=True)
class WeatherRisk:
    active: bool
    reason: str
    severity: float  # 0..1 penalty multiplier on HOS feasibility contribution


def midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    return (lat1 + lat2) / 2, (lon1 + lon2) / 2


def assess_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    force_severe: bool = False,
) -> WeatherRisk:
    if force_severe:
        # ponytail: demo fixture when live weather is clear
        return WeatherRisk(True, "Demo: severe winter storm on corridor", 0.45)

    key = getattr(settings, "OPENWEATHER_API_KEY", "") or ""
    if not key:
        return WeatherRisk(False, "", 0.0)

    lat, lon = midpoint(origin_lat, origin_lon, dest_lat, dest_lon)
    cache_key = f"owm:{lat:.2f}:{lon:.2f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return WeatherRisk(**cached)

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={key}"
    )
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return WeatherRisk(False, "", 0.0)

    weather = (data.get("weather") or [{}])[0]
    wid = int(weather.get("id") or 0)
    desc = str(weather.get("description") or "")
    wind = float((data.get("wind") or {}).get("speed") or 0)
    severe = wid in SEVERE_IDS or wind >= 20  # m/s ~ high wind
    risk = WeatherRisk(
        active=severe,
        reason=f"Weather: {desc}" if severe else "",
        severity=0.4 if severe else 0.0,
    )
    cache.set(
        cache_key,
        {"active": risk.active, "reason": risk.reason, "severity": risk.severity},
        CACHE_TTL,
    )
    return risk
