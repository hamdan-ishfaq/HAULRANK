from django.urls import path

from .views import RankView

urlpatterns = [
    path("rank/", RankView.as_view(), name="rank"),
]
