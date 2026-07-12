"""DRF exception handler — never leak settings/tracebacks when DEBUG is off."""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("haulrank")


def haulrank_exception_handler(exc, context):
    request = context.get("request")
    rid = getattr(request, "request_id", "-") if request else "-"
    path = getattr(request, "path", "-") if request else "-"

    response = drf_exception_handler(exc, context)
    if response is not None:
        logger.warning(
            "rid=%s path=%s handled_exc=%s status=%s detail=%s",
            rid,
            path,
            type(exc).__name__,
            response.status_code,
            response.data,
        )
        return response

    logger.exception(
        "rid=%s path=%s unhandled_exc=%s",
        rid,
        path,
        type(exc).__name__,
        exc_info=exc,
    )
    if settings.DEBUG:
        return None
    return Response(
        {"detail": "Internal server error", "request_id": rid},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
