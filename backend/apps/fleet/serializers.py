from rest_framework import serializers

from .models import Driver, Truck
from .reliability import reliability_score


class DriverSerializer(serializers.ModelSerializer):
    reliability_score = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = (
            "hos_hours_remaining",
            "home_base_lat",
            "home_base_lon",
            "preferred_markets",
            "no_go_markets",
            "hos_violations_90d",
            "inspection_pass_rate",
            "on_time_pct",
            "reliability_score",
            "compliance_state",
            "compliance_reason",
            "compliance_checked_at",
        )
        read_only_fields = (
            "compliance_state",
            "compliance_reason",
            "compliance_checked_at",
            "reliability_score",
        )

    def get_reliability_score(self, obj):
        return reliability_score(
            obj.hos_violations_90d, obj.inspection_pass_rate, obj.on_time_pct
        )


class TruckSerializer(serializers.ModelSerializer):
    driver = DriverSerializer(required=False, allow_null=True)

    class Meta:
        model = Truck
        fields = (
            "id",
            "equipment_type",
            "current_lat",
            "current_lon",
            "mpg",
            "driver",
        )
        read_only_fields = ("id",)

    def validate_mpg(self, value):
        if value <= 0:
            raise serializers.ValidationError("mpg must be > 0")
        return value

    def create(self, validated_data):
        driver_data = validated_data.pop("driver", None)
        truck = Truck.objects.create(**validated_data)
        if driver_data:
            Driver.objects.create(truck=truck, **driver_data)
        return truck

    def update(self, instance, validated_data):
        driver_data = validated_data.pop("driver", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if driver_data is not None:
            Driver.objects.update_or_create(truck=instance, defaults=driver_data)
        return instance
