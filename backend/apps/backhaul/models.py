from django.db import models

from apps.loads.models import Load


class TripChain(models.Model):
    outbound = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="chains_out")
    return_load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="chains_return")
    combined_score = models.FloatField()
    total_deadhead_miles = models.FloatField()
    total_hours = models.FloatField(default=0)
    total_rate_usd = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
