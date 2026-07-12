from rest_framework import serializers

from .models import Load


class LoadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Load
        fields = (
            "id",
            "origin_lat",
            "origin_lon",
            "dest_lat",
            "dest_lon",
            "dest_market",
            "miles",
            "rate_usd",
            "equipment_type",
            "pickup_window_start",
            "pickup_window_end",
            "est_transit_hours",
        )
        read_only_fields = ("id",)

    def validate_miles(self, value):
        if value <= 0:
            raise serializers.ValidationError("miles must be > 0")
        return value

    def validate_rate_usd(self, value):
        if value < 0:
            raise serializers.ValidationError("rate_usd must be >= 0")
        return value

    def validate(self, attrs):
        start = attrs.get("pickup_window_start") or getattr(
            self.instance, "pickup_window_start", None
        )
        end = attrs.get("pickup_window_end") or getattr(
            self.instance, "pickup_window_end", None
        )
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"pickup_window_end": "must be after pickup_window_start"}
            )
        return attrs
