from unittest.mock import patch

from apps.weather.service import annotate_weather
from apps.scoring.engine import LoadInput, ScoreResult
from integrations.openweather import WeatherRisk, assess_route


def test_demo_severe_flags_load():
    loads = [
        LoadInput(1, 32.7, -96.8, 29.7, -95.3, "TX", 200, 700, "dry_van", 4),
        LoadInput(2, 32.7, -96.8, 35.4, -97.5, "OK", 200, 700, "dry_van", 4),
    ]
    ranked = [
        ScoreResult(1, 1, 0, 1, 1, 1, 0.9, 10, 3.5),
        ScoreResult(2, 1, 0, 1, 1, 1, 0.8, 10, 3.5),
    ]
    annotated = annotate_weather(loads, ranked, demo_load_id=1)
    by_id = {a["load_id"]: a for a in annotated}
    assert by_id[1]["weather_risk"] is True
    assert by_id[1]["overall_adjusted"] < 0.9


def test_open_meteo_calm(monkeypatch):
    monkeypatch.setattr("integrations.openweather.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("integrations.openweather.cache.set", lambda *a, **k: None)
    monkeypatch.setattr(
        "integrations.openweather._from_open_meteo",
        lambda lat, lon: WeatherRisk(False, "", 0.0),
    )
    risk = assess_route(32.7, -96.8, 29.7, -95.3)
    assert risk.active is False


def test_open_meteo_severe(monkeypatch):
    monkeypatch.setattr("integrations.openweather.cache.get", lambda *a, **k: None)
    monkeypatch.setattr("integrations.openweather.cache.set", lambda *a, **k: None)
    monkeypatch.setattr(
        "integrations.openweather._from_open_meteo",
        lambda lat, lon: WeatherRisk(True, "Open-Meteo: WMO 95", 0.4),
    )
    risk = assess_route(32.7, -96.8, 29.7, -95.3)
    assert risk.active is True
    assert "95" in risk.reason
