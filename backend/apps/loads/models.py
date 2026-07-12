from django.db import models


class Load(models.Model):
    class Equipment(models.TextChoices):
        DRY_VAN = "dry_van", "Dry Van"
        REEFER = "reefer", "Reefer"
        FLATBED = "flatbed", "Flatbed"

    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    dest_lat = models.FloatField()
    dest_lon = models.FloatField()
    dest_market = models.CharField(max_length=40)
    miles = models.FloatField()
    rate_usd = models.FloatField()
    equipment_type = models.CharField(max_length=40, choices=Equipment.choices)
    pickup_window_start = models.DateTimeField()
    pickup_window_end = models.DateTimeField()
    est_transit_hours = models.FloatField()

    def __str__(self) -> str:
        return f"{self.dest_market} {self.miles}mi ${self.rate_usd}"
