from django.urls import path

from .views import CopilotView

urlpatterns = [
    path("copilot/", CopilotView.as_view(), name="copilot"),
]
