"""Lane rate history + z-score benchmarking."""

from __future__ import annotations

from statistics import mean, pstdev

from django.db import models


class LaneRateHistory(models.Model):
    dest_market = models.CharField(max_length=40, db_index=True)
    week_start = models.DateField()
    avg_rate_per_mile = models.FloatField()

    class Meta:
        unique_together = ("dest_market", "week_start")
        ordering = ["-week_start"]


def benchmark(rate_per_mile: float, history_rpms: list[float]) -> dict:
    if len(history_rpms) < 2:
        return {"z_score": 0.0, "flag": "typical", "lane_avg": rate_per_mile}
    avg = mean(history_rpms)
    sd = pstdev(history_rpms) or 1e-6
    z = (rate_per_mile - avg) / sd
    if z <= -1.0:
        flag = "below_market"
    elif z >= 1.0:
        flag = "above_market"
    else:
        flag = "typical"
    return {"z_score": round(z, 3), "flag": flag, "lane_avg": round(avg, 3)}
