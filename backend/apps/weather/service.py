"""Apply weather risk onto ranked results (post-score annotation)."""

from __future__ import annotations

from apps.scoring.engine import LoadInput, ScoreResult
from integrations.openweather import WeatherRisk, assess_route


def annotate_weather(
    loads: list[LoadInput],
    ranked: list[ScoreResult],
    *,
    demo_load_id: int | None = None,
) -> list[dict]:
    by_id = {l.id: l for l in loads}
    out = []
    for r in ranked:
        load = by_id[r.load_id]
        risk: WeatherRisk = assess_route(
            load.origin_lat,
            load.origin_lon,
            load.dest_lat,
            load.dest_lon,
            force_severe=(demo_load_id is not None and load.id == demo_load_id),
        )
        adj_overall = r.overall
        if risk.active:
            adj_overall = max(0.0, r.overall * (1.0 - risk.severity * 0.5))
        out.append(
            {
                "load_id": r.load_id,
                "weather_risk": risk.active,
                "weather_status": risk.status,
                "weather_reason": risk.reason,
                "overall_adjusted": adj_overall,
            }
        )
    return out
