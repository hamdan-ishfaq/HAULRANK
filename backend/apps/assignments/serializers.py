from rest_framework import serializers

from apps.fleet.models import Truck
from apps.fleet.reliability import eligible_for_high_value
from apps.scoring.engine import LoadInput, TruckInput, is_feasible

from .models import ACTIVE_STATUSES, Assignment


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ("id", "load", "truck", "status", "status_history")
        read_only_fields = ("id", "status_history", "status")

    def validate_truck(self, truck: Truck):
        user = self.context["request"].user
        if truck.carrier.owner_id != user.id:
            raise serializers.ValidationError("Truck not yours")
        return truck

    def validate(self, attrs):
        load = attrs["load"]
        truck = attrs["truck"]

        taken = Assignment.objects.filter(load=load, status__in=ACTIVE_STATUSES).exists()
        if taken:
            raise serializers.ValidationError({"load": "Load already assigned"})

        truck = Truck.objects.select_related("driver").get(pk=truck.pk)
        if not hasattr(truck, "driver"):
            raise serializers.ValidationError({"truck": "Truck has no driver"})
        driver = truck.driver

        state = driver.compliance_state or "clear"
        if state == "suspended":
            raise serializers.ValidationError(
                {
                    "truck": (
                        "Driver compliance suspended — dispatch eligibility revoked"
                        + (f" ({driver.compliance_reason})" if driver.compliance_reason else "")
                    )
                }
            )

        if state == "restricted" or not eligible_for_high_value(
            driver.reliability_score, load.rate_usd
        ):
            if load.rate_usd >= 2000:
                raise serializers.ValidationError(
                    {
                        "load": (
                            "High-value load gated by compliance "
                            f"(state={state}, reliability={driver.reliability_score})"
                        )
                    }
                )

        truck_in = TruckInput(
            id=truck.id,
            equipment_type=truck.equipment_type,
            lat=truck.current_lat,
            lon=truck.current_lon,
            mpg=truck.mpg,
            hos_hours_remaining=driver.hos_hours_remaining,
            preferred_markets=list(driver.preferred_markets or []),
            no_go_markets=list(driver.no_go_markets or []),
        )
        load_in = LoadInput(
            id=load.id,
            origin_lat=load.origin_lat,
            origin_lon=load.origin_lon,
            dest_lat=load.dest_lat,
            dest_lon=load.dest_lon,
            dest_market=load.dest_market,
            miles=load.miles,
            rate_usd=load.rate_usd,
            equipment_type=load.equipment_type,
            est_transit_hours=load.est_transit_hours,
        )
        if not is_feasible(truck_in, load_in):
            raise serializers.ValidationError(
                {"load": "Load is not HOS/equipment feasible for this truck"}
            )
        return attrs


class AssignmentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Assignment.Status.choices)
