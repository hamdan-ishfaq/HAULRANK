from django.urls import path

from .views import ExplainView

urlpatterns = [
    path("rank/<int:score_run_id>/explain/", ExplainView.as_view(), name="rank-explain"),
]
