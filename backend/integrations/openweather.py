"""Route weather risk via Open-Meteo (no API key). OpenWeather optional fallback."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from django.conf import settings
from django.core.cache import cache

CACHE_TTL = 60 * 60 * 3

# WMO weather interpretation codes (Open-Meteo) that imply disruption
SEVERE_WMO = {
    65,
    67,  # heavy rain / freezing rain
    75,
    77,  # heavy snow / snow grains
    82,
    86,  # heavy showers
    95,
    96,
    99,  # thunderstorm (+ hail)
}

# OpenWeather condition ids (optional provider)
SEVERE_OWM = {
    202,
    212,
    221,
    230,
    231,
    232,
    502,
    503,
    504,
    511,
    522,
    531,
    602,
    622,
    616,
    771,
    781,
}


@dataclass(frozen=True)
class WeatherRisk:
    active: bool
    reason: str
    severity: float  # 0..1


def midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    return (lat1 + lat2) / 2, (lon1 + lon2) / 2


def _from_open_meteo(lat: float, lon: float) -> WeatherRisk | None:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=weather_code,wind_speed_10m"
        "&wind_speed_unit=ms"
    )
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            cur = resp.json().get("current") or {}
    except Exception:
        return None

    code = int(cur.get("weather_code") or 0)
    wind = float(cur.get("wind_speed_10m") or 0)
    severe = code in SEVERE_WMO or wind >= 20
    if not severe:
        return WeatherRisk(False, "", 0.0)
    reason = f"Open-Meteo: WMO {code}" + (f", wind {wind:.0f} m/s" if wind >= 20 else "")
    return WeatherRisk(True, reason, 0.4)


def _from_openweather(lat: float, lon: float, key: str) -> WeatherRisk | None:
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
        return None

    weather = (data.get("weather") or [{}])[0]
    wid = int(weather.get("id") or 0)
    desc = str(weather.get("description") or "")
    wind = float((data.get("wind") or {}).get("speed") or 0)
    severe = wid in SEVERE_OWM or wind >= 20
    if not severe:
        return WeatherRisk(False, "", 0.0)
    return WeatherRisk(True, f"Weather: {desc}", 0.4)


def assess_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    force_severe: bool = False,
) -> WeatherRisk:
    if force_severe:
        return WeatherRisk(True, "Demo: severe winter storm on corridor", 0.45)

    lat, lon = midpoint(origin_lat, origin_lon, dest_lat, dest_lon)
    cache_key = f"wx:{lat:.2f}:{lon:.2f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return WeatherRisk(**cached)

    risk = _from_open_meteo(lat, lon)
    if risk is None:
        key = getattr(settings, "OPENWEATHER_API_KEY", "") or ""
        risk = _from_openweather(lat, lon, key) if key else None
    if risk is None:
        # fail open — no live weather available
        return WeatherRisk(False, "", 0.0)

    cache.set(
        cache_key,
        {"active": risk.active, "reason": risk.reason, "severity": risk.severity},
        CACHE_TTL,
    )
    return risk
