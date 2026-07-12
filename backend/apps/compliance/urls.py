from django.urls import path

from .views import CompliancePollView, ComplianceSummaryView

urlpatterns = [
    path("compliance/", ComplianceSummaryView.as_view(), name="compliance-summary"),
    path("compliance/poll/", CompliancePollView.as_view(), name="compliance-poll"),
]
