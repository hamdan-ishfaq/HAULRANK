from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.fleet.urls")),
    path("api/", include("apps.loads.urls")),
    path("api/", include("apps.scoring.urls")),
    path("api/", include("apps.explain.urls")),
    path("api/", include("apps.assignments.urls")),
]
