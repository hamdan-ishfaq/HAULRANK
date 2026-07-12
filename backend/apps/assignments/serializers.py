from rest_framework import serializers

from apps.fleet.models import Truck

from .models import Assignment


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
        # block second active assignment for same load once accepted+
        taken = Assignment.objects.filter(
            load=load,
            status__in=[
                Assignment.Status.ACCEPTED,
                Assignment.Status.DISPATCHED,
                Assignment.Status.DELIVERED,
            ],
        ).exists()
        if taken:
            raise serializers.ValidationError({"load": "Load already assigned"})
        return attrs


class AssignmentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Assignment.Status.choices)
