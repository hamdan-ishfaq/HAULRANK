from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.compliance.service import poll_all_drivers, verdict_for_driver
from apps.fleet.models import Driver


class ComplianceSummaryView(APIView):
    """Fleet compliance snapshot for the logged-in carrier."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        drivers = (
            Driver.objects.filter(truck__carrier__owner=request.user)
            .select_related("truck")
            .order_by("truck_id")
        )
        rows = []
        counts = {"clear": 0, "watch": 0, "restricted": 0, "suspended": 0}
        for d in drivers:
            state = d.compliance_state or "clear"
            counts[state] = counts.get(state, 0) + 1
            live = verdict_for_driver(d)
            rows.append(
                {
                    "truck_id": d.truck_id,
                    "compliance_state": state,
                    "compliance_reason": d.compliance_reason,
                    "compliance_checked_at": d.compliance_checked_at,
                    "reliability_score": d.reliability_score,
                    "live_state": live.state,
                    "live_drift": live.state != state,
                    "can_dispatch": state != "suspended",
                    "high_value_allowed": state in ("clear", "watch"),
                }
            )
        return Response({"counts": counts, "drivers": rows})


class CompliancePollView(APIView):
    """Staff/demo: run one poll cycle (same as management command)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        dry = bool(request.data.get("dry_run") if isinstance(request.data, dict) else False)
        summary = poll_all_drivers(dry_run=dry, owner=request.user)
        return Response(summary)
