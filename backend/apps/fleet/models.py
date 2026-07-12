from django.conf import settings
from django.db import models


class Carrier(models.Model):
    name = models.CharField(max_length=120)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carrier",
    )

    def __str__(self) -> str:
        return self.name


class Truck(models.Model):
    class Equipment(models.TextChoices):
        DRY_VAN = "dry_van", "Dry Van"
        REEFER = "reefer", "Reefer"
        FLATBED = "flatbed", "Flatbed"

    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name="trucks")
    equipment_type = models.CharField(max_length=40, choices=Equipment.choices)
    current_lat = models.FloatField()
    current_lon = models.FloatField()
    mpg = models.FloatField(default=6.5)

    def __str__(self) -> str:
        return f"{self.equipment_type}#{self.pk}"


class Driver(models.Model):
    truck = models.OneToOneField(Truck, on_delete=models.CASCADE, related_name="driver")
    hos_hours_remaining = models.FloatField()
    home_base_lat = models.FloatField()
    home_base_lon = models.FloatField()
    preferred_markets = models.JSONField(default=list)
    no_go_markets = models.JSONField(default=list)
    # Tier 3 — synthetic compliance signals (Sentinel-echo)
    hos_violations_90d = models.PositiveIntegerField(default=0)
    inspection_pass_rate = models.FloatField(default=0.95)
    on_time_pct = models.FloatField(default=0.90)

    def __str__(self) -> str:
        return f"driver@{self.truck_id}"

    @property
    def reliability_score(self) -> float:
        from apps.fleet.reliability import reliability_score

        return reliability_score(
            self.hos_violations_90d,
            self.inspection_pass_rate,
            self.on_time_pct,
        )
