from apps.weather.service import annotate_weather
from apps.scoring.engine import LoadInput, ScoreResult


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
    assert "storm" in by_id[1]["weather_reason"].lower() or by_id[1]["weather_reason"]
    assert by_id[1]["overall_adjusted"] < 0.9
    assert by_id[2]["weather_risk"] is False


def test_fail_open_without_key(settings):
    settings.OPENWEATHER_API_KEY = ""
    loads = [LoadInput(1, 32.7, -96.8, 29.7, -95.3, "TX", 200, 700, "dry_van", 4)]
    ranked = [ScoreResult(1, 1, 0, 1, 1, 1, 0.9, 10, 3.5)]
    annotated = annotate_weather(loads, ranked)
    assert annotated[0]["weather_risk"] is False
