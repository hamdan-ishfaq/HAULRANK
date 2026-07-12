from django.db import models

from apps.fleet.models import Truck
from apps.loads.models import Load


class ScoreRun(models.Model):
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, related_name="score_runs")
    created_at = models.DateTimeField(auto_now_add=True)
    diesel_usd_per_gal = models.FloatField()

    def __str__(self) -> str:
        return f"ScoreRun#{self.pk} truck={self.truck_id}"


class ScoreBreakdown(models.Model):
    score_run = models.ForeignKey(ScoreRun, related_name="results", on_delete=models.CASCADE)
    load = models.ForeignKey(Load, on_delete=models.CASCADE)
    rate_per_mile_score = models.FloatField()
    deadhead_penalty = models.FloatField()
    fuel_efficiency_score = models.FloatField()
    hos_feasibility = models.FloatField()
    market_preference_score = models.FloatField()
    overall = models.FloatField()
    deadhead_miles = models.FloatField(default=0)
    rate_per_mile = models.FloatField(default=0)
    rank = models.PositiveIntegerField()
    explanation_text = models.TextField(blank=True)

    class Meta:
        ordering = ["rank"]

    def __str__(self) -> str:
        return f"#{self.rank} load={self.load_id} overall={self.overall:.3f}"
