from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Assignment
from .serializers import AssignmentSerializer, AssignmentStatusSerializer


class AssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Assignment.objects.filter(
            truck__carrier__owner=self.request.user
        ).select_related("load", "truck", "truck__driver")

    def partial_update(self, request, *args, **kwargs):
        ser = AssignmentStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            assignment = self.get_object()
            assignment.transition_to(
                ser.validated_data["status"], by=request.user.username
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AssignmentSerializer(assignment).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        assignment = self.get_object()
        return Response({"id": assignment.id, "history": assignment.status_history})
