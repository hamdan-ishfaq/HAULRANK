from rest_framework.response import Response
from rest_framework.views import APIView

from apps.assignments.models import Assignment
from apps.fleet.models import Truck
from apps.scoring.models import ScoreBreakdown


class AnalyticsSummaryView(APIView):
    def get(self, request):
        trucks = Truck.objects.filter(carrier__owner=request.user)
        truck_ids = list(trucks.values_list("id", flat=True))

        delivered = Assignment.objects.filter(
            truck_id__in=truck_ids, status=Assignment.Status.DELIVERED
        ).select_related("load")
        revenue_by_truck: dict[int, float] = {t: 0.0 for t in truck_ids}
        for a in delivered:
            revenue_by_truck[a.truck_id] = revenue_by_truck.get(a.truck_id, 0.0) + float(
                a.load.rate_usd
            )

        all_a = Assignment.objects.filter(truck_id__in=truck_ids)
        total = all_a.count()
        accepted = all_a.exclude(status=Assignment.Status.OFFERED).count()
        acceptance_rate = (accepted / total) if total else 0.0

        breakdowns = ScoreBreakdown.objects.filter(score_run__truck_id__in=truck_ids)
        deadheads = list(breakdowns.values_list("deadhead_miles", flat=True)[:500])
        avg_deadhead = sum(deadheads) / len(deadheads) if deadheads else 0.0

        accepted_load_ids = set(
            all_a.exclude(status=Assignment.Status.OFFERED).values_list("load_id", flat=True)
        )
        scores_all = list(breakdowns.values_list("overall", "load_id")[:500])
        avg_all = sum(s for s, _ in scores_all) / len(scores_all) if scores_all else 0.0
        acc_scores = [s for s, lid in scores_all if lid in accepted_load_ids]
        avg_accepted = sum(acc_scores) / len(acc_scores) if acc_scores else 0.0

        return Response(
            {
                "revenue_by_truck": [
                    {"truck_id": tid, "revenue_usd": round(rev, 2)}
                    for tid, rev in revenue_by_truck.items()
                ],
                "acceptance_rate": round(acceptance_rate, 3),
                "avg_deadhead_miles": round(avg_deadhead, 1),
                "avg_score_all": round(avg_all, 3),
                "avg_score_accepted": round(avg_accepted, 3),
                "assignment_count": total,
                "delivered_count": delivered.count(),
            }
        )
