from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scoring.models import ScoreRun

from .service import explain_top_n


class ExplainView(APIView):
    def post(self, request, score_run_id: int):
        try:
            run = ScoreRun.objects.select_related("truck__carrier").get(
                pk=score_run_id, truck__carrier__owner=request.user
            )
        except ScoreRun.DoesNotExist:
            return Response({"detail": "Score run not found"}, status=404)

        if not run.results.exists():
            return Response({"detail": "No results to explain"}, status=400)

        try:
            rows = explain_top_n(run, n=3)
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            return Response(
                {"detail": "Explanation service unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "score_run_id": run.id,
                "explanations": [
                    {
                        "rank": r.rank,
                        "load_id": r.load_id,
                        "overall": r.overall,
                        "explanation_text": r.explanation_text,
                    }
                    for r in rows
                ],
            }
        )
