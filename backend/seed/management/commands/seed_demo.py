"""Seed synthetic demo data. Labeled synthetic in README."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.assignments.models import Assignment
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
        parser.add_argument(
            "--brownfield",
            action="store_true",
            help=(
                "Create locked accepted/dispatched assignments so fleet optimize "
                "only fills residual demand (planning analogy, not a digital twin)."
            ),
        )

    def handle(self, *args, **options):
        if options["flush"]:
            Assignment.objects.all().delete()
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
            # eq, city, hos, pref, nogo, violations, insp, ontime
            # Dallas HOS 14h so the seeded backhaul round-trip is HOS-feasible
            ("dry_van", "Dallas", 14.0, ["TX", "OK"], ["NY"], 0, 0.98, 0.94),
            ("reefer", "Houston", 8.0, ["TX"], [], 1, 0.92, 0.88),
            ("flatbed", "OKC", 11.0, ["OK", "TX"], [], 0, 0.96, 0.91),
            ("dry_van", "Austin", 4.0, ["TX"], [], 4, 0.70, 0.60),  # weak compliance
            ("dry_van", "Memphis", 9.0, ["TN", "GA"], [], 0, 0.95, 0.90),
        ]
        if Truck.objects.filter(carrier=carrier).count() < len(profiles):
            Truck.objects.filter(carrier=carrier).delete()
            for eq, city, hos, pref, nogo, viol, insp, ontime in profiles:
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
                    hos_violations_90d=viol,
                    inspection_pass_rate=insp,
                    on_time_pct=ontime,
                )

        for truck, profile in zip(
            Truck.objects.filter(carrier=carrier).select_related("driver").order_by("id"),
            profiles,
        ):
            _, _, _, _, _, viol, insp, ontime = profile
            if hasattr(truck, "driver") and truck.driver is not None:
                Driver.objects.filter(pk=truck.driver.pk).update(
                    hos_violations_90d=viol,
                    inspection_pass_rate=insp,
                    on_time_pct=ontime,
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

        # Guaranteed Dallas↔Houston dry_van round-trip that beats best single on $/hr.
        # Idempotent: wipe prior demo-tagged loads by unique rate/miles fingerprint.
        start = timezone.now()
        dallas, houston = CITIES["Dallas"], CITIES["Houston"]
        Load.objects.filter(
            equipment_type="dry_van",
            miles=240.0,
            rate_usd__in=[720.0, 1250.0],
            dest_market="TX",
        ).filter(
            origin_lat__in=[dallas[0], houston[0]],
        ).delete()
        Load.objects.create(
            origin_lat=dallas[0],
            origin_lon=dallas[1],
            dest_lat=houston[0],
            dest_lon=houston[1],
            dest_market="TX",
            miles=240.0,
            rate_usd=720.0,
            equipment_type="dry_van",
            pickup_window_start=start,
            pickup_window_end=start + timedelta(hours=8),
            est_transit_hours=4.5,
        )
        Load.objects.create(
            origin_lat=houston[0],
            origin_lon=houston[1],
            dest_lat=dallas[0],
            dest_lon=dallas[1],
            dest_market="TX",
            miles=240.0,
            rate_usd=1250.0,
            equipment_type="dry_van",
            pickup_window_start=start + timedelta(hours=6),
            pickup_window_end=start + timedelta(hours=14),
            est_transit_hours=4.5,
        )

        # Keep Dallas driver HOS aligned even if trucks already existed
        dallas_truck = (
            Truck.objects.filter(carrier=carrier, equipment_type="dry_van")
            .select_related("driver")
            .order_by("id")
            .first()
        )
        if dallas_truck and hasattr(dallas_truck, "driver"):
            Driver.objects.filter(pk=dallas_truck.driver.pk).update(hos_hours_remaining=14.0)

        if options.get("brownfield"):
            self._seed_brownfield_locks(carrier)

        call_command("seed_rates")
        call_command("poll_compliance")
        locks = Assignment.objects.filter(
            truck__carrier=carrier,
            status__in=("accepted", "dispatched"),
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded carrier={carrier.name} trucks={Truck.objects.filter(carrier=carrier).count()} "
                f"loads={Load.objects.count()} locked={locks} "
                f"(user=demo / demo-pass-123)"
            )
        )

    def _seed_brownfield_locks(self, carrier: Carrier) -> None:
        """Two committed assignments — residual trucks optimize around them."""
        trucks = list(
            Truck.objects.filter(carrier=carrier).select_related("driver").order_by("id")
        )
        if len(trucks) < 2:
            return
        dallas = trucks[0]
        houston = next(
            (t for t in trucks if abs(t.current_lat - 29.76) < 0.2),
            trucks[1],
        )
        # Prefer the seeded Dallas→Houston dry_van 240mi/$720 load
        dh = (
            Load.objects.filter(
                equipment_type="dry_van",
                miles=240.0,
                rate_usd=720.0,
            )
            .order_by("id")
            .first()
        )
        other = (
            Load.objects.filter(equipment_type=houston.equipment_type)
            .exclude(pk=dh.pk if dh else None)
            .order_by("id")
            .first()
        )
        def _lock(load, truck, status: str) -> None:
            Assignment.objects.filter(
                load=load, status__in=("offered", "accepted", "dispatched")
            ).exclude(truck=truck).delete()
            row = Assignment.objects.filter(
                load=load, status__in=("offered", "accepted", "dispatched")
            ).first()
            hist = [
                {
                    "status": status,
                    "at": timezone.now().isoformat(),
                    "by": "seed_brownfield",
                }
            ]
            if row:
                row.truck = truck
                row.status = status
                row.status_history = hist
                row.save(update_fields=["truck", "status", "status_history"])
            else:
                Assignment.objects.create(
                    load=load, truck=truck, status=status, status_history=hist
                )

        if dh:
            _lock(dh, dallas, Assignment.Status.DISPATCHED)
        if other and (dh is None or other.pk != dh.pk):
            _lock(other, houston, Assignment.Status.ACCEPTED)
        self.stdout.write("  brownfield locks: Dallas dispatched + Houston accepted")
