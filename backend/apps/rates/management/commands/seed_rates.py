from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.rates.models import LaneRateHistory

MARKETS = ["TX", "OK", "TN", "GA", "IL", "AZ"]


class Command(BaseCommand):
    help = "Seed ~12 weeks of synthetic lane rate history"

    def handle(self, *args, **options):
        today = date.today()
        n = 0
        for market in MARKETS:
            base = {"TX": 2.6, "OK": 2.4, "TN": 2.5, "GA": 2.55, "IL": 2.7, "AZ": 2.45}[market]
            for w in range(12):
                week = today - timedelta(weeks=w)
                # mild weekly noise
                rpm = base + 0.05 * ((w % 3) - 1) + 0.02 * (hash(market + str(w)) % 5)
                LaneRateHistory.objects.update_or_create(
                    dest_market=market,
                    week_start=week,
                    defaults={"avg_rate_per_mile": round(rpm, 3)},
                )
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {n} lane-rate rows"))
