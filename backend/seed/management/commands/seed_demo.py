"""Seed synthetic demo data. Labeled synthetic in README."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load

User = get_user_model()

# A few US city coords for synthetic origins/dests
CITIES = {
    "Dallas": (32.7767, -96.7970, "TX"),
    "Houston": (29.7604, -95.3698, "TX"),
    "OKC": (35.4676, -97.5164, "OK"),
    "Austin": (30.2672, -97.7431, "TX"),
    "Memphis": (35.1495, -90.0490, "TN"),
    "Atlanta": (33.7490, -84.3880, "GA"),
    "Chicago": (41.8781, -87.6298, "IL"),
    "Phoenix": (33.4484, -112.0740, "AZ"),
}


class Command(BaseCommand):
    help = "Seed synthetic trucks/loads for demo (idempotent with --flush)"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true")

    def handle(self, *args, **options):
        if options["flush"]:
            Load.objects.all().delete()
            Truck.objects.all().delete()
            Carrier.objects.all().delete()
            User.objects.filter(username="demo").delete()

        user, created = User.objects.get_or_create(username="demo")
        user.set_password("demo-pass-123")
        user.is_active = True
        user.save()

        carrier, _ = Carrier.objects.get_or_create(
            owner=user, defaults={"name": "Demo Carrier"}
        )

        profiles = [
            ("dry_van", "Dallas", 10.0, ["TX", "OK"], ["NY"]),
            ("reefer", "Houston", 8.0, ["TX"], []),
            ("flatbed", "OKC", 11.0, ["OK", "TX"], []),
            ("dry_van", "Austin", 4.0, ["TX"], []),  # tight HOS
            ("dry_van", "Memphis", 9.0, ["TN", "GA"], []),
        ]
        if Truck.objects.filter(carrier=carrier).count() < len(profiles):
            Truck.objects.filter(carrier=carrier).delete()
            for eq, city, hos, pref, nogo in profiles:
                lat, lon, _ = CITIES[city]
                t = Truck.objects.create(
                    carrier=carrier,
                    equipment_type=eq,
                    current_lat=lat,
                    current_lon=lon,
                    mpg=6.5,
                )
                Driver.objects.create(
                    truck=t,
                    hos_hours_remaining=hos,
                    home_base_lat=lat,
                    home_base_lon=lon,
                    preferred_markets=pref,
                    no_go_markets=nogo,
                )

        if Load.objects.count() < 50:
            Load.objects.all().delete()
            start = timezone.now()
            names = list(CITIES.keys())
            n = 0
            for i, origin in enumerate(names):
                for dest in names:
                    if origin == dest:
                        continue
                    o_lat, o_lon, _ = CITIES[origin]
                    d_lat, d_lon, market = CITIES[dest]
                    # crude miles from index spacing
                    miles = 150 + ((i * 37 + n * 17) % 800)
                    eq = ["dry_van", "reefer", "flatbed"][n % 3]
                    transit = max(2.0, miles / 55.0)
                    Load.objects.create(
                        origin_lat=o_lat,
                        origin_lon=o_lon,
                        dest_lat=d_lat,
                        dest_lon=d_lon,
                        dest_market=market,
                        miles=float(miles),
                        rate_usd=round(miles * (2.2 + (n % 5) * 0.15), 2),
                        equipment_type=eq,
                        pickup_window_start=start + timedelta(hours=n % 12),
                        pickup_window_end=start + timedelta(hours=12 + (n % 12)),
                        est_transit_hours=round(transit, 2),
                    )
                    n += 1
                    if n >= 80:
                        break
                if n >= 80:
                    break

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded carrier={carrier.name} trucks={Truck.objects.filter(carrier=carrier).count()} "
                f"loads={Load.objects.count()} (user=demo / demo-pass-123)"
            )
        )
